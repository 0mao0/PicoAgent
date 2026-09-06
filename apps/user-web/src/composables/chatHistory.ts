/**
 * 聊天历史持久化（localStorage 实现）。
 * 接口形状（listSessions/saveSession/removeSession）为将来切换
 * aichat-api 服务端持久化预留，届时仅替换本文件实现，UI 层不动。
 */
export interface ChatSessionRecord {
  id: string
  scene: string
  title: string
  updatedAt: number
  messages: unknown[]
}

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

export const CHAT_HISTORY_STORAGE_KEY = 'ag_chat_history_v1'
export const MAX_SESSIONS_PER_LIBRARY = 50

function readAll(storage: StorageLike): Record<string, ChatSessionRecord[]> {
  try {
    const raw = storage.getItem(CHAT_HISTORY_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed as Record<string, ChatSessionRecord[]>
  } catch {
    return {}
  }
}

function writeAll(storage: StorageLike, data: Record<string, ChatSessionRecord[]>): void {
  try {
    storage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(data))
  } catch (error) {
    // 配额超限或隐私模式：跳过本次持久化，不影响会话本身
    console.warn('[chatHistory] 写入聊天历史失败，已跳过本次:', error)
  }
}

/** 会话标题：首条非空用户消息压缩空白后截断 30 字 */
export function deriveTitle(messages: Array<{ role?: string; content?: unknown }>): string {
  const firstUser = messages.find(m => m.role === 'user' && String(m.content ?? '').trim())
  const text = String(firstUser?.content ?? '').trim().replace(/\s+/g, ' ')
  if (!text) return '未命名对话'
  return text.length > 30 ? `${text.slice(0, 30)}…` : text
}

/** 指定库的会话列表（更新时间倒序）；损坏条目被丢弃并顺带写回清理 */
export function listSessions(storage: StorageLike, libraryId: string): ChatSessionRecord[] {
  const all = readAll(storage)
  const list = Array.isArray(all[libraryId]) ? all[libraryId] : []
  const valid = list.filter(record =>
    record && typeof record === 'object' &&
    typeof record.id === 'string' &&
    Array.isArray(record.messages)
  )
  if (valid.length !== list.length) {
    all[libraryId] = valid
    writeAll(storage, all)
  }
  return [...valid].sort((a, b) => b.updatedAt - a.updatedAt)
}

/** 插入或更新会话；超过上限淘汰最旧更新的会话 */
export function saveSession(storage: StorageLike, libraryId: string, record: ChatSessionRecord): void {
  const all = readAll(storage)
  const list = Array.isArray(all[libraryId]) ? all[libraryId] : []
  const next = [...list.filter(item => item?.id !== record.id), record]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_SESSIONS_PER_LIBRARY)
  all[libraryId] = next
  writeAll(storage, all)
}

/** 删除指定库中指定 id 的会话 */
export function removeSession(storage: StorageLike, libraryId: string, sessionId: string): void {
  const all = readAll(storage)
  const list = Array.isArray(all[libraryId]) ? all[libraryId] : []
  all[libraryId] = list.filter(item => item?.id !== sessionId)
  writeAll(storage, all)
}
