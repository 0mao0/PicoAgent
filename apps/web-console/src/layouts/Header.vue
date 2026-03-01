<template>
  <div class="app-header">
    <div class="header-left">
      <div class="app-logo">
        <span class="logo-icon">🧠</span>
        <span class="app-name">AnGIneer</span>
      </div>
    </div>
    
    <div class="header-center">
      <span class="project-name">{{ projectName }}</span>
    </div>
    
    <div class="header-right">
      <a-space>
        <a-button type="text" @click="toggleTheme">
          <span class="theme-icon">{{ themeIcon }}</span>
        </a-button>
        <a-button type="text" @click="openSettings">
          <SettingOutlined />
        </a-button>
        <a-button type="text">
          <UserOutlined />
        </a-button>
      </a-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { SettingOutlined, UserOutlined } from '@ant-design/icons-vue'
import { useThemeStore } from '@/stores'

const themeStore = useThemeStore()

const projectName = ref('未命名项目')

const themeIcon = computed(() => {
  return themeStore.isDark ? '☀️' : '🌙'
})

const toggleTheme = () => {
  themeStore.toggleTheme()
}

const openSettings = () => {
  console.log('Open settings')
}

onMounted(() => {
  themeStore.initTheme()
})
</script>

<style lang="less" scoped>
.app-header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: #1f1f1f;
  color: #fff;
  flex-shrink: 0;
  border-bottom: 1px solid #333;
}

.header-left {
  display: flex;
  align-items: center;
}

.app-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;

  .logo-icon {
    font-size: 20px;
  }

  .app-name {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.project-name {
  font-size: 14px;
  color: #999;
}

.header-right {
  display: flex;
  align-items: center;

  :deep(.ant-btn) {
    color: #fff;
    &:hover {
      color: #667eea;
    }
  }

  .theme-icon {
    font-size: 18px;
  }
}
</style>
