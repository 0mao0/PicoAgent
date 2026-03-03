/**
 * AI 对话状态管理 - 与 web-console 保持一致
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { ChatRequest } from '@angineer/docs-ui'

/** 消息角色 */
type MessageRole = 'system' | 'user' | 'assistant'

/** 消息对象 */
interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: number
  tokens?: number
}

/**
 * 生成唯一消息 ID
 */
const generateMessageId = (): string => {
  return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * 估算 token 数量（简化版）
 */
const estimateTokens = (content: string): number => {
  let tokens = 0
  for (const char of content) {
    if (/[\u4e00-\u9fa5]/.test(char)) {
      tokens += 1.5
    } else {
      tokens += 0.5
    }
  }
  return Math.ceil(tokens)
}

/**
 * 管理上下文（滑动窗口 + 压缩）
 */
const manageContext = (
  messages: Message[],
  maxRounds: number = 10,
  maxTokens: number = 4000
): Message[] => {
  // 保留系统消息
  const systemMessages = messages.filter((m: Message) => m.role === 'system')

  // 获取对话消息（用户和助手）
  let chatMessages = messages.filter((m: Message) => m.role !== 'system')

  // 滑动窗口：保留最近 N 轮对话
  const userMessages = chatMessages.filter((m: Message) => m.role === 'user')
  if (userMessages.length > maxRounds) {
    const removeCount = (userMessages.length - maxRounds) * 2
    chatMessages = chatMessages.slice(removeCount)
  }

  // Token 压缩：如果超出限制，压缩历史消息
  let totalTokens = 0
  for (const msg of chatMessages) {
    totalTokens += estimateTokens(msg.content)
  }

  if (totalTokens > maxTokens) {
    // 压缩策略：从后往前保留，直到接近限制
    const compressed: Message[] = []
    let currentTokens = 0

    // 从后往前保留，直到接近限制
    for (let i = chatMessages.length - 1; i >= 0; i--) {
      const msg = chatMessages[i]
      const tokens = estimateTokens(msg.content)

      if (currentTokens + tokens < maxTokens * 0.8) {
        compressed.unshift(msg)
        currentTokens += tokens
      } else {
        break
      }
    }

    chatMessages = compressed
  }

  return [...systemMessages, ...chatMessages]
}

export const useChatStore = defineStore('chat', () => {
  // ===== State =====
  const messages = ref<Message[]>([])
  const loading = ref(false)
  const currentStreamContent = ref('')
  const availableModels = ref<Array<{ value: string; label: string }>>([])
  const selectedModel = ref('')
  const abortController = ref<AbortController | null>(null)

  // ===== Getters =====
  const contextInfo = computed(() => {
    const userMessages = messages.value.filter((m: Message) => m.role === 'user')

    let totalTokens = 0
    for (const msg of messages.value) {
      totalTokens += estimateTokens(msg.content)
    }

    return {
      rounds: userMessages.length,
      totalMessages: messages.value.length,
      estimatedTokens: totalTokens
    }
  })

  // ===== Actions =====

  /**
   * 获取可用模型列表
   */
  const fetchModels = async () => {
    try {
      const response = await fetch('/api/llm_configs')
      if (response.ok) {
        const data = await response.json()
        availableModels.value = data
          .filter((m: any) => m.configured)
          .map((m: any) => ({
            value: m.name,
            label: m.name
          }))

        // 设置默认模型
        if (!selectedModel.value && availableModels.value.length > 0) {
          const qwenModel = availableModels.value.find(m =>
            m.value.includes('Qwen2.5-7B') || m.value.includes('qwen2.5-7b')
          )
          selectedModel.value = qwenModel?.value || availableModels.value[0].value
        }
      }
    } catch (error) {
      console.error('获取模型列表失败:', error)
    }
  }

  /**
   * 发送流式消息
   */
  const sendMessage = async (
    content: string,
    onChunk?: (chunk: string) => void
  ): Promise<void> => {
    if (!content.trim() || loading.value) return

    // 添加用户消息
    const userMessage: Message = {
      id: generateMessageId(),
      role: 'user',
      content: content.trim(),
      timestamp: Date.now()
    }
    messages.value.push(userMessage)

    loading.value = true
    currentStreamContent.value = ''

    // 管理上下文
    const managedMessages = manageContext([...messages.value])

    // 准备请求
    const request: ChatRequest = {
      message: userMessage.content,
      history: managedMessages.filter(m => m.role !== 'system'),
      model: selectedModel.value,
      mode: 'chat'
    }

    // 创建 AbortController
    abortController.value = new AbortController()

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify(request),
        signal: abortController.value.signal
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      // 读取流式响应
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantMessageId = generateMessageId()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)

            if (data === '[DONE]') {
              break
            }

            try {
              const event = JSON.parse(data)

              switch (event.type) {
                case 'start':
                  assistantMessageId = event.messageId || assistantMessageId
                  break

                case 'chunk':
                  currentStreamContent.value += event.content || ''
                  onChunk?.(event.content || '')
                  break

                case 'end':
                  // 保存助手消息
                  messages.value.push({
                    id: assistantMessageId,
                    role: 'assistant',
                    content: currentStreamContent.value,
                    timestamp: Date.now()
                  })
                  currentStreamContent.value = ''
                  break

                case 'error':
                  throw new Error(event.error || 'Stream error')
              }
            } catch (e) {
              console.error('解析 SSE 数据失败:', e)
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('用户中断生成')
        // 保存已生成的内容
        if (currentStreamContent.value) {
          messages.value.push({
            id: generateMessageId(),
            role: 'assistant',
            content: currentStreamContent.value,
            timestamp: Date.now()
          })
        }
      } else {
        console.error('发送消息失败:', error)
        // 添加错误消息
        messages.value.push({
          id: generateMessageId(),
          role: 'assistant',
          content: `抱歉，对话出现错误：${error.message}`,
          timestamp: Date.now()
        })
      }
    } finally {
      loading.value = false
      currentStreamContent.value = ''
      abortController.value = null
    }
  }

  /**
   * 停止生成
   */
  const stopGeneration = () => {
    if (abortController.value) {
      abortController.value.abort()
    }
  }

  /**
   * 清空对话
   */
  const clearMessages = () => {
    messages.value = []
    currentStreamContent.value = ''
  }

  /**
   * 设置选中的模型
   */
  const setSelectedModel = (model: string) => {
    selectedModel.value = model
  }

  return {
    // State
    messages,
    loading,
    currentStreamContent,
    availableModels,
    selectedModel,
    // Getters
    contextInfo,
    // Actions
    fetchModels,
    sendMessage,
    stopGeneration,
    clearMessages,
    setSelectedModel
  }
})
