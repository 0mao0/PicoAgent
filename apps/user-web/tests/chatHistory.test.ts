import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  MAX_SESSIONS_PER_LIBRARY,
  deriveTitle,
  listSessions,
  removeSession,
  saveSession,
} from '../src/composables/chatHistory.ts'

function createMemoryStorage() {
  const map = new Map<string, string>()
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => { map.set(key, value) },
  }
}

function makeRecord(id: string, updatedAt: number, content = 'q') {
  return {
    id,
    scene: 'docs',
    title: `会话 ${id}`,
    updatedAt,
    messages: [{ role: 'user', content }],
  }
}

test('deriveTitle 取首条用户消息并截断 30 字', () => {
  assert.equal(deriveTitle([{ role: 'assistant', content: 'x' }, { role: 'user', content: '  多行\n问题  ' }]), '多行 问题')
  assert.equal(deriveTitle([{ role: 'user', content: '长'.repeat(40) }]).length, 31) // 30 + 省略号
  assert.equal(deriveTitle([]), '未命名对话')
})

test('saveSession 插入/去重更新，listSessions 按更新时间倒序', () => {
  const storage = createMemoryStorage()
  saveSession(storage, 'libA', makeRecord('a', 100))
  saveSession(storage, 'libB', makeRecord('b', 50))
  saveSession(storage, 'libA', makeRecord('a', 200))
  saveSession(storage, 'libA', makeRecord('c', 150))
  assert.deepEqual(listSessions(storage, 'libA').map(r => r.id), ['a', 'c'])
  assert.deepEqual(listSessions(storage, 'libB').map(r => r.id), ['b'])
})

test('saveSession 超过上限按最旧更新时间淘汰', () => {
  const storage = createMemoryStorage()
  for (let i = 0; i < MAX_SESSIONS_PER_LIBRARY + 10; i += 1) {
    saveSession(storage, 'libA', makeRecord(`s${i}`, i))
  }
  const list = listSessions(storage, 'libA')
  assert.equal(list.length, MAX_SESSIONS_PER_LIBRARY)
  assert.equal(list[0].id, `s${MAX_SESSIONS_PER_LIBRARY + 9}`)
})

test('removeSession 删除指定会话', () => {
  const storage = createMemoryStorage()
  saveSession(storage, 'libA', makeRecord('a', 1))
  saveSession(storage, 'libA', makeRecord('b', 2))
  removeSession(storage, 'libA', 'a')
  assert.deepEqual(listSessions(storage, 'libA').map(r => r.id), ['b'])
})

test('损坏数据容错：非法 JSON 返回空数组，坏条目被清理且好条目保留', () => {
  const storage = createMemoryStorage()
  storage.setItem('ag_chat_history_v1', '{broken json')
  assert.deepEqual(listSessions(storage, 'libA'), [])
  storage.setItem('ag_chat_history_v1', JSON.stringify({ libA: [null, 'bad', makeRecord('ok', 9)] }))
  assert.deepEqual(listSessions(storage, 'libA').map(r => r.id), ['ok'])
})
