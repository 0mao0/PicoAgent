<template>
  <div class="chat-panel-container">
    <div class="chat-messages" ref="messagesRef">
      <div v-for="msg in messages" :key="msg.id" :class="['message', msg.role]">
        <div class="message-content">
          <div v-if="msg.role === 'user'" class="user-message">
            {{ msg.content }}
          </div>
          <div v-else class="assistant-message">
            <div v-html="renderMarkdown(msg.content)" />
            <div v-if="msg.references?.length" class="references">
              <a-divider style="margin: 8px 0" />
              <div class="ref-title">参考来源:</div>
              <a-tag v-for="ref in msg.references" :key="ref.id" color="blue">
                {{ ref.title }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input">
      <div class="context-hint" v-if="contextItems.length">
        <a-tag v-for="item in contextItems" :key="item.id" closable @close="removeContext(item.id)">
          {{ item.title }}
        </a-tag>
      </div>
      <a-textarea
        v-model:value="inputText"
        placeholder="输入消息，@ 引用知识库内容..."
        :auto-size="{ minRows: 2, maxRows: 6 }"
        @keydown.enter.ctrl="sendMessage"
      />
      <div class="input-actions">
        <a-select
          v-model:value="selectedModel"
          class="model-selector-small"
          size="small"
        >
          <a-select-option value="gpt-4">GPT-4</a-select-option>
          <a-select-option value="gpt-3.5-turbo">GPT-3.5 Turbo</a-select-option>
          <a-select-option value="claude-3">Claude 3</a-select-option>
          <a-select-option value="local">本地模型</a-select-option>
        </a-select>
        <a-button type="primary" @click="sendMessage" :loading="loading">
          发送
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const selectedModel = ref('gpt-4')
const inputText = ref('')
const loading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)

const messages = computed(() => chatStore.messages)
const contextItems = computed(() => chatStore.contextItems)

const renderMarkdown = (content: string) => {
  return content
}

const sendMessage = async () => {
  if (!inputText.value.trim()) return
  
  loading.value = true
  try {
    await chatStore.sendMessage(inputText.value, selectedModel.value)
    inputText.value = ''
  } finally {
    loading.value = false
  }
}

const removeContext = (id: string) => {
  chatStore.removeContextItem(id)
}
</script>

<style lang="less" scoped>
@import '@/styles/variables.less';

.chat-panel-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 1px solid @border-color-light;
  transition: background-color 0.3s, border-color 0.3s;

  :global(html.dark) & {
    background: @dark-background-color-light;
    border-left-color: @dark-border-color-light;
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;

  .message {
    margin-bottom: 16px;

    &.user {
      .user-message {
        background: #1890ff;
        color: #fff;
        padding: 8px 12px;
        border-radius: 8px;
        display: inline-block;
        max-width: 80%;
        float: right;
      }
    }

    &.assistant {
      .assistant-message {
        background: #f5f5f5;
        padding: 12px;
        border-radius: 8px;
        max-width: 90%;
        transition: background-color 0.3s;
      }

      :global(html.dark) & .assistant-message {
        background: @dark-border-color-light;
      }
    }
  }

  .references {
    margin-top: 8px;
    .ref-title {
      font-size: 12px;
      color: #666;
      margin-bottom: 4px;
      transition: color 0.3s;
    }

    :global(html.dark) & .ref-title {
      color: @dark-text-color-secondary;
    }
  }
}

.chat-input {
  padding: 12px;
  border-top: 1px solid @border-color-light;
  transition: border-color 0.3s;

  :global(html.dark) & {
    border-top-color: @dark-border-color-light;
  }

  .context-hint {
    margin-bottom: 8px;
  }

  .input-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
    gap: 8px;

    .model-selector-small {
      flex: 1;
      max-width: 200px;
      font-size: 12px;
    }
  }
}
</style>
