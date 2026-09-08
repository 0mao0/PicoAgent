/**
 * 共享会话 token。
 *
 * 背景：userweb(3005) 与 adminweb(3002) 在开发环境是不同端口/不同 origin，各有一份独立的
 * localStorage，无法互通；更关键的是它们各自登录会创建两个独立的**后端会话**，因此登出其一时，
 * 另一个会话仍然有效，表现为「一个退了、另一个不退」。
 *
 * 方案：把会话 token 存到 **host cookie**（cookie 按域名共享、不含端口），3002/3005/生产同源
 * 都能读到同一把 key。任一应用登录时写 cookie（唯一会话），退出时清 cookie + 删后端会话，
 * 其它应用在重新打开/获得焦点/同源标签页 storage 变化时重读 cookie，一旦为空即同步退出。
 *
 * cookie 仅作为前端存储与跨应用同步载体；请求鉴权仍走 Authorization: Bearer（后端契约不变）。
 */
const COOKIE_NAME = 'ag_session_token'
/** 与后端 SESSION_TTL_DAYS(7) 对齐，保证 cookie 与后端会话生命周期一致 */
const MAX_AGE = 7 * 24 * 3600

function readCookie(): string {
  if (typeof document === 'undefined') return ''
  const cookie = document.cookie.split(/;\s*/)
  for (const part of cookie) {
    const eq = part.indexOf('=')
    if (eq < 0) continue
    const key = part.slice(0, eq).trim()
    if (key === COOKIE_NAME) return decodeURIComponent(part.slice(eq + 1))
  }
  return ''
}

/** 会话 token 唯一真相源：cookie（跨应用共享）。 */
export function getSessionToken(): string {
  return readCookie()
}

export function setSessionToken(token: string): void {
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(token)}; path=/; SameSite=Lax; Max-Age=${MAX_AGE}`
  // 同步写 localStorage：用于同源标签页间触发 storage 事件做即时登出同步（cookie 变化不触发事件）
  localStorage.setItem(COOKIE_NAME, token)
}

export function clearSessionToken(): void {
  document.cookie = `${COOKIE_NAME}=; path=/; SameSite=Lax; Max-Age=0`
  localStorage.removeItem(COOKIE_NAME)
}

/**
 * 跨应用/跨标签页会话同步监听：
 * - storage：同源其它标签页改动 localStorage（登录/登出）时即时触发；
 * - focus：切换到本标签页（跨端口用户直接从另一个应用切过来）时重读 cookie。
 * 二者都会调用 onSync（各应用实现为：重读 token，为空则登出，否则刷新用户信息）。
 */
export function bindSessionSync(onSync: () => void | Promise<void>): () => void {
  const handler = () => { void onSync() }
  window.addEventListener('focus', handler)
  window.addEventListener('storage', handler)
  return () => {
    window.removeEventListener('focus', handler)
    window.removeEventListener('storage', handler)
  }
}
