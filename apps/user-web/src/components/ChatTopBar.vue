<template>
  <header class="chat-top-bar">
    <div class="brand">
      <img src="/favicon.svg" alt="AnGIneer logo" class="brand-logo" />
      <span class="brand-name">AnGIneer</span>
      <a-popover
        v-if="releaseNotes"
        trigger="hover"
        placement="bottomLeft"
        :overlay-style="{ maxWidth: '560px' }"
      >
        <template #title>v{{ appVersion }} 发版内容</template>
        <template #content>
          <div class="release-notes">
            <div v-for="(line, idx) in releaseNoteLines" :key="idx" class="release-notes__line">
              <span class="release-notes__dot" />{{ line }}
            </div>
          </div>
        </template>
        <span v-if="appVersion" class="brand-version">v{{ appVersion }}</span>
      </a-popover>
      <span v-else-if="appVersion" class="brand-version">v{{ appVersion }}</span>
    </div>
    <div class="top-actions">
      <a-tooltip title="功能开发中，敬请期待">
        <a-button type="text" class="top-btn" @click="workbenchTodo">
          <template #icon><AppstoreOutlined /></template>
          工作台
        </a-button>
      </a-tooltip>
      <a-tooltip>
        <template #title>{{ isDark ? '切换到浅色模式' : '切换到深色模式' }}</template>
        <a-button
          type="text"
          class="top-btn"
          :aria-label="isDark ? '切换到浅色模式' : '切换到深色模式'"
          @click="toggleTheme"
        >
          <template #icon>
            <BulbFilled v-if="isDark" />
            <BulbOutlined v-else />
          </template>
        </a-button>
      </a-tooltip>
      <a-tooltip title="历史对话">
        <a-button type="text" class="top-btn" aria-label="历史对话" @click="emit('openHistory')">
          <template #icon><HistoryOutlined /></template>
        </a-button>
      </a-tooltip>
      <a-dropdown placement="bottomRight">
        <a-button type="text" class="top-btn user-menu-btn">
          <UserOutlined class="user-icon" />
          <span class="user-name">{{ displayName }}</span>
        </a-button>
        <template #overlay>
          <a-menu @click="onUserMenuClick">
            <a-menu-item key="logout">
              <template #icon><LogoutOutlined /></template>
              退出登录
            </a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
/**
 * 对话首页极简顶栏：品牌（logo+名称+版本，hover 版本看发版内容）+ 工作台占位 /
 * 主题灯泡 / 历史 / 用户菜单（点用户名 → 退出登录）。
 */
import { computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  BulbFilled,
  BulbOutlined,
  HistoryOutlined,
  LogoutOutlined,
  UserOutlined
} from '@ant-design/icons-vue'
import { useTheme } from '@angineer/ui-kit'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits<{ openHistory: [] }>()
const { isDark, toggleTheme } = useTheme()
const authStore = useAuthStore()

const appVersion = import.meta.env.VITE_APP_VERSION || ''
const releaseNotes = import.meta.env.VITE_APP_RELEASE_NOTES || ''
/** 摘要按全/半角分号拆条，逐条换行展示 */
const releaseNoteLines = computed(() =>
  releaseNotes.split(/[；;]/).map(line => line.trim()).filter(Boolean)
)

const displayName = computed(
  () => authStore.user?.display_name || authStore.user?.username || '未登录'
)

const workbenchTodo = () => {
  message.info('工作台待开发')
}

const onUserMenuClick = async ({ key }: { key: string | number }) => {
  if (key === 'logout') {
    await authStore.logout()
  }
}
</script>

<style lang="less" scoped>
.chat-top-bar {
  flex-shrink: 0;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);

  .brand {
    display: flex;
    align-items: center;
    gap: 8px;

    .brand-logo {
      width: 22px;
      height: 22px;
      display: block;
    }

    .brand-name {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .brand-version {
      font-size: 12px;
      color: var(--text-tertiary);
      cursor: default;
    }
  }

  .top-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .top-btn {
    color: var(--text-secondary);
  }

  .user-menu-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    max-width: 200px;

    .user-icon {
      font-size: 14px;
    }

    .user-name {
      font-size: 13px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

.release-notes {
  max-height: 280px;
  overflow-y: auto;

  .release-notes__line {
    display: flex;
    gap: 6px;
    font-size: 12px;
    line-height: 1.7;
    color: var(--text-secondary);
    word-break: break-word;

    & + .release-notes__line {
      margin-top: 6px;
    }
  }

  .release-notes__dot {
    flex-shrink: 0;
    width: 4px;
    height: 4px;
    margin-top: 8px;
    border-radius: 50%;
    background: var(--primary-color, #1890ff);
  }
}
</style>
