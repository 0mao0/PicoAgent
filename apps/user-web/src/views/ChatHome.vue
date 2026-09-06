<template>
  <div class="chat-home">
    <ChatTopBar @open-history="historyOpen = true" />
    <div class="chat-body">
      <div class="chat-col">
        <AIChat
          :key="scene"
          ref="aiChatRef"
          class="chat-instance"
          title=""
          :hero="!hasConversation"
          :show-context-info="false"
          :scene="scene"
          :session-id="sessionId"
          :library-id="libraryId"
          :transport="defaultAIChatTransport"
          @send="hasConversation = true"
          @messages-change="onMessagesChange"
          @select-citation="handleCitationSelect"
        >
          <template #hero>
            <h1 class="hero-title">今天，想查点什么？</h1>
            <div class="hero-scene-chips">
              <button
                type="button"
                :class="{ active: scene === 'docs' }"
                @click="scene = 'docs'"
              >知识库问答</button>
              <button
                type="button"
                :class="{ active: scene === 'sops' }"
                @click="scene = 'sops'"
              >SOP 问答</button>
            </div>
          </template>
        </AIChat>
      </div>
      <aside v-if="panelDocId" class="citation-panel">
        <div class="panel-head">
          <span class="panel-title" :title="panelTitle">{{ panelTitle }}</span>
          <a-button type="text" size="small" aria-label="关闭溯源面板" @click="closePanel">
            <template #icon><CloseOutlined /></template>
          </a-button>
        </div>
        <div class="panel-body">
          <DocumentView
            ref="docViewRef"
            :doc-id="panelDocId"
            :library-id="panelLibraryId"
            :title="panelTitle"
            :side-panel-open="false"
          />
        </div>
      </aside>
    </div>
    <HistoryDrawer
      v-model:open="historyOpen"
      :sessions="sessions"
      :current-session-id="sessionId"
      @restore="restoreSession"
      @remove="deleteSession"
      @new-chat="startNewChat"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 对话优先首页：
 * - Hero 态（无消息）：AIChat hero 模式，居中大输入框 + 场景 chip；
 * - 对话态：同一 AIChat 实例展示消息流；点引用在右侧溯源面板（复用 DocumentView
 *   的 PDF/Markdown 分支与 bbox 定位）打开目标文档并定位；
 * - 历史：@messagesChange 落盘 localStorage（chatHistory.ts），抽屉恢复。
 */
import { computed, nextTick, ref } from 'vue'
import { CloseOutlined } from '@ant-design/icons-vue'
import { AIChat } from '@angineer/aichat-ui'
import type { AIChatMessage, AIChatCitation } from '@angineer/aichat-ui'
import DocumentView from '@/views/DocumentView.vue'
import ChatTopBar from '@/components/ChatTopBar.vue'
import HistoryDrawer from '@/components/HistoryDrawer.vue'
import { defaultAIChatTransport } from '../../../shared/chatTransport'
import { useAuthStore } from '@/stores/auth'
import {
  deriveTitle,
  listSessions,
  removeSession,
  saveSession,
} from '@/composables/chatHistory'
import type { ChatSessionRecord } from '@/composables/chatHistory'

const authStore = useAuthStore()
const libraryId = computed(() => authStore.libraryId || 'default')

const aiChatRef = ref<InstanceType<typeof AIChat> | null>(null)
const docViewRef = ref<InstanceType<typeof DocumentView> | null>(null)

const scene = ref<'docs' | 'sops'>('docs')
const sessionId = ref(`chat-${Date.now().toString(36)}`)
const hasConversation = ref(false)
const historyOpen = ref(false)
const sessions = ref<ChatSessionRecord[]>([])

/** 溯源面板 */
const panelDocId = ref('')
const panelTitle = ref('')
const panelLibraryId = ref('default')

const refreshSessions = () => {
  sessions.value = listSessions(localStorage, libraryId.value)
}
refreshSessions()

const onMessagesChange = (messages: AIChatMessage[]) => {
  if (!messages.length) return // 新会话/清空不落空记录
  hasConversation.value = true
  saveSession(localStorage, libraryId.value, {
    id: sessionId.value,
    scene: scene.value,
    title: deriveTitle(messages),
    updatedAt: Date.now(),
    messages: messages.filter(m => m.role !== 'system'),
  })
  refreshSessions()
}

const handleCitationSelect = async (citation: AIChatCitation) => {
  if (!citation?.doc_id) return
  panelDocId.value = citation.doc_id
  panelTitle.value = citation.doc_title || citation.doc_id
  panelLibraryId.value = libraryId.value
  await nextTick()
  // DocumentView 内部有 pending 队列：先于文档加载完成调用也安全
  docViewRef.value?.focusCitation?.(citation as any)
}

const closePanel = () => {
  panelDocId.value = ''
  panelTitle.value = ''
}

const restoreSession = async (record: ChatSessionRecord) => {
  historyOpen.value = false
  closePanel()
  scene.value = record.scene === 'sops' ? 'sops' : 'docs'
  sessionId.value = record.id
  await nextTick() // 等 :key 重建 / sessionId watch 切会话完成
  aiChatRef.value?.loadSession(record.messages as AIChatMessage[])
  hasConversation.value = true
}

const deleteSession = (id: string) => {
  removeSession(localStorage, libraryId.value, id)
  refreshSessions()
}

const startNewChat = () => {
  historyOpen.value = false
  closePanel()
  aiChatRef.value?.startNewChat?.() // 内部：停止生成 + 清消息 + 换会话 key
  sessionId.value = `chat-${Date.now().toString(36)}` // 与内部新 key 对齐
  hasConversation.value = false
}
</script>

<style lang="less" scoped>
.chat-home {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.chat-body {
  flex: 1;
  min-height: 0;
  display: flex;
  position: relative;
}

.chat-col {
  flex: 1;
  min-width: 0;
  display: flex;
}

.chat-instance {
  flex: 1;
}

.citation-panel {
  width: 55%;
  min-width: 420px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border-color);
  background: var(--bg-secondary);

  .panel-head {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid var(--border-color);

    .panel-title {
      font-size: 13px;
      color: var(--text-secondary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .panel-body {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
}

@media (max-width: 1023px) {
  .citation-panel {
    position: absolute;
    inset: 0;
    width: 100%;
    min-width: 0;
    z-index: 20;
  }
}

.hero-title {
  font-size: 28px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary);
}

.hero-scene-chips {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-bottom: 8px;

  button {
    padding: 4px 14px;
    border-radius: 14px;
    border: 1px solid var(--border-color);
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 13px;

    &.active {
      color: var(--primary-color);
      border-color: var(--primary-color);
    }
  }
}
</style>
