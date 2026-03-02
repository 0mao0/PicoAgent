<template>
  <div class="app-header" :class="{ 'dark-mode': themeStore.isDark }">
    <div class="header-left">
      <div class="app-logo">
        <svg class="logo-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 20C7.59 20 4 16.41 4 12C4 7.59 7.59 4 12 4C16.41 4 20 7.59 20 12C20 16.41 16.41 20 12 20ZM12.5 7H11V13L16.25 16.15L17 14.92L12.5 12.25V7Z" fill="url(#gradient)"/>
          <defs>
            <linearGradient id="gradient" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
              <stop stop-color="#667eea"/>
              <stop offset="1" stop-color="#764ba2"/>
            </linearGradient>
          </defs>
        </svg>
        <span class="app-name">AnGIneer</span>
      </div>
    </div>
    
    <div class="header-center">
      <span class="project-name">{{ projectName }}</span>
    </div>
    
    <div class="header-right">
      <a-space size="small">
        <a-button type="text" @click="toggleTheme" class="theme-btn">
          <BulbFilled v-if="themeStore.isDark" />
          <BulbOutlined v-else />
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
import { ref, onMounted } from 'vue'
import { SettingOutlined, UserOutlined, BulbOutlined, BulbFilled } from '@ant-design/icons-vue'
import { useThemeStore } from '@/stores'

const themeStore = useThemeStore()

const projectName = ref('未命名项目')

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
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  transition: all 0.3s ease;
  backdrop-filter: blur(8px);
}

.app-header:not(.dark-mode) {
  background: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.88);
}

.app-header.dark-mode {
  background: rgba(20, 20, 20, 0.9);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.85);
}

.header-left {
  display: flex;
  align-items: center;
}

.app-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.3px;

  .logo-icon {
    width: 28px;
    height: 28px;
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
  padding: 4px 12px;
  border-radius: 6px;
  font-weight: 500;
}

.app-header:not(.dark-mode) .project-name {
  color: rgba(0, 0, 0, 0.45);
  background: rgba(0, 0, 0, 0.02);
}

.app-header.dark-mode .project-name {
  color: rgba(255, 255, 255, 0.45);
  background: rgba(255, 255, 255, 0.04);
}

.header-right {
  display: flex;
  align-items: center;

  :deep(.ant-btn) {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  :deep(.ant-btn svg) {
    font-size: 18px;
  }

  .app-header:not(.dark-mode) & :deep(.ant-btn) {
    color: rgba(0, 0, 0, 0.65);
    &:hover {
      color: #667eea;
      background: rgba(102, 126, 234, 0.08);
    }
  }

  .app-header.dark-mode & :deep(.ant-btn) {
    color: rgba(255, 255, 255, 0.65);
    &:hover {
      color: #667eea;
      background: rgba(102, 126, 234, 0.15);
    }
  }
}
</style>
