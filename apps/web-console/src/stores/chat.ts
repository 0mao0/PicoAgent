/**
 * AI 对话 Store
 * 提供全局 AI 对话状态管理和流式对话功能
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 消息角色类型
export type MessageRole = 'user' | 'assistant' | 'system'

// 聊天消息
export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: number
  // 多模态预留
  images?: string[]
}

// 上下文项
export interface ContextItem {
  id: string
  type: 'document' | 'table' | 'formula' | 'sop'
  title: string
  content: string
}

// 模型选项
export interface ModelOption {
  value: string
  label: string
}

// 流式响应事件类型
export type StreamEventType = 'start' | 'chunk' | 'end' | 'error'

// 流式响应事件
export interface ChatStreamEvent {
  type: StreamEventType
  messageId?: string
  content?: string
  usage?: {
    promptTokens: number
    completionTokens: number
  }
  error?: string
}

// 对话请求参数
export interface ChatRequest {
  message: string
  history: Message[]
  model?: string
  mode?: 'chat' | 'reasoning' | 'vision'
  context?: {
    references?: string[]
    [key: string]: any
  }
}

// 上下文管理配置
interface ContextConfig {
  maxRounds: number
  enableCompression: boolean
  compressionThreshold: number
}

// 默认上下文配置
const DEFAULT_CONTEXT_CONFIG: ContextConfig = {
  maxRounds: 10,
  enableCompression: true,
  compressionThreshold: 4000
}

/**
 * 估算消息的 token 数量
 */
function estimateTokens(message: Message): number {
  const content = message.content || ''
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
 * 管理对话上下文
 */
function manageContext(
  messages: Message[],
  config: ContextConfig = DEFAULT_CONTEXT_CONFIG
): Message[] {
  const systemMessages = messages.filter(m => m.role === 'system')
  let chatMessages = messages.filter(m => m.role !== 'system')

  // 滑动窗口
  if (config.maxRounds > 0) {
    const userMessageCount = chatMessages.filter(m => m.role === 'user').length
    if (userMessageCount > config.maxRounds) {
      const messagesToRemove = (userMessageCount - config.maxRounds) * 2
      chatMessages = chatMessages.slice(messagesToRemove)
    }
  }

  // 上下文压缩
  if (config.enableCompression) {
    let totalTokens = chatMessages.reduce((sum, m) => sum + estimateTokens(m), 0)
    while (totalTokens > config.compressionThreshold && chatMessages.length > 2) {
      const removed = chatMessages.splice(0, 2)
      totalTokens -= removed.reduce((sum, m) => sum + estimateTokens(m), 0)
    }
  }

  return [...systemMessages, ...chatMessages]
}

export const useChatStore = defineStore('chat', () => {
  // 状态
  const messages = ref<Message[]>([])
  const contextItems = ref<ContextItem[]>([])
  const loading = ref(false)
  const currentStreamContent = ref('')
  const selectedModel = ref('')
  const availableModels = ref<ModelOption[]>([])
  const abortController = ref<AbortController | null>(null)

  // 计算属性
  const contextTokens = computed(() => {
    return messages.value.reduce((sum, m) => sum + estimateTokens(m), 0)
  })

  const contextRounds = computed(() => {
    return messages.value.filter(m => m.role === 'user').length
  })

  /**
   * 生成唯一消息 ID
   */
  const generateMessageId = (): string => {
    return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * 添加消息
   */
  const addMessage = (message: Omit<Message, 'id' | 'timestamp'>) => {
    messages.value.push({
      ...message,
      id: generateMessageId(),
      timestamp: Date.now()
    })
  }

  /**
   * 添加上下文项
   */
  const addContextItem = (item: ContextItem) => {
    if (!contextItems.value.find(i => i.id === item.id)) {
      contextItems.value.push(item)
    }
  }

  /**
   * 移除上下文项
   */
  const removeContextItem = (id: string) => {
    const index = contextItems.value.findIndex(i => i.id === id)
    if (index > -1) {
      contextItems.value.splice(index, 1)
    }
  }

  /**
   * 清空上下文
   */
  const clearContext = () => {
    contextItems.value = []
  }

  /**
   * 清空消息
   */
  const clearMessages = () => {
    messages.value = []
    currentStreamContent.value = ''
  }

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
            const data = line.slice(6).trim()
            if (data === '[DONE]') continue

            try {
              const event: ChatStreamEvent = JSON.parse(data)

              switch (event.type) {
                case 'start':
                  if (event.messageId) {
                    assistantMessageId = event.messageId
                  }
                  break

                case 'chunk':
                  if (event.content) {
                    currentStreamContent.value += event.content
                    onChunk?.(event.content)
                  }
                  break

                case 'end':
                  // 流结束，添加助手消息
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
              console.error('Parse SSE data error:', e)
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Request aborted')
        if (currentStreamContent.value) {
          messages.value.push({
            id: generateMessageId(),
            role: 'assistant',
            content: currentStreamContent.value + '\n\n[已停止生成]',
            timestamp: Date.now()
          })
        }
      } else {
        console.error('Chat error:', error)
        messages.value.push({
          id: generateMessageId(),
          role: 'assistant',
          content: `抱歉，对话出现错误：${error instanceof Error ? error.message : '未知错误'}`,
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

  return {
    // 状态
    messages,
    contextItems,
    loading,
    currentStreamContent,
    selectedModel,
    availableModels,
    // 计算属性
    contextTokens,
    contextRounds,
    // 方法
    addMessage,
    addContextItem,
    removeContextItem,
    clearContext,
    clearMessages,
    fetchModels,
    sendMessage,
    stopGeneration,
    generateMessageId
  }
})
