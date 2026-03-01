import { defineStore } from 'pinia'
import { ref } from 'vue'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  references?: { id: string; title: string }[]
  timestamp: number
}

interface ContextItem {
  id: string
  type: 'document' | 'table' | 'formula' | 'sop'
  title: string
  content: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const contextItems = ref<ContextItem[]>([])
  const loading = ref(false)

  const addMessage = (message: Omit<Message, 'id' | 'timestamp'>) => {
    messages.value.push({
      ...message,
      id: `msg-${Date.now()}`,
      timestamp: Date.now()
    })
  }

  const addContextItem = (item: ContextItem) => {
    if (!contextItems.value.find(i => i.id === item.id)) {
      contextItems.value.push(item)
    }
  }

  const removeContextItem = (id: string) => {
    const index = contextItems.value.findIndex(i => i.id === id)
    if (index > -1) {
      contextItems.value.splice(index, 1)
    }
  }

  const clearContext = () => {
    contextItems.value = []
  }

  const sendMessage = async (content: string, model: string) => {
    addMessage({ role: 'user', content })
    
    loading.value = true
    try {
      addMessage({
        role: 'assistant',
        content: `这是一个模拟回复。您的问题是：${content}`,
        references: [
          { id: 'ref-1', title: '海港总体设计规范 6.4.5' }
        ]
      })
    } finally {
      loading.value = false
    }
  }

  const clearMessages = () => {
    messages.value = []
  }

  return {
    messages,
    contextItems,
    loading,
    addMessage,
    addContextItem,
    removeContextItem,
    clearContext,
    sendMessage,
    clearMessages
  }
})
