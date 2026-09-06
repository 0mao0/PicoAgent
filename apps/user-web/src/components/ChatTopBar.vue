<template>
  <header class="chat-top-bar">
    <span class="brand">AnGIneer</span>
    <div class="top-actions">
      <a-button type="text" class="top-btn" @click="router.push('/workspace')">
        <template #icon><AppstoreOutlined /></template>
        工作台
      </a-button>
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
    </div>
  </header>
</template>

<script setup lang="ts">
/** 对话首页极简顶栏：只有 工作台入口 / 主题灯泡 / 历史 三个控件（退出登录在历史抽屉内） */
import { useRouter } from 'vue-router'
import { AppstoreOutlined, BulbFilled, BulbOutlined, HistoryOutlined } from '@ant-design/icons-vue'
import { useTheme } from '@angineer/ui-kit'

const emit = defineEmits<{ openHistory: [] }>()
const router = useRouter()
const { isDark, toggleTheme } = useTheme()
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
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .top-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .top-btn {
    color: var(--text-secondary);
  }
}
</style>
