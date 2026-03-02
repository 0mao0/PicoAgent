<template>
  <a-config-provider :locale="zhCN" :theme="theme">
    <div class="app-container" :class="{ 'dark-mode': themeStore.isDark }">
      <Header />
      <SplitPanes 
        class="main-content" 
        :initial-left-ratio="0.2"
        :initial-right-ratio="0.2"
        @resize="handleResize"
      >
        <template #left>
          <LeftPanel />
        </template>
        <template #center>
          <Workbench />
        </template>
        <template #right>
          <ChatPanel />
        </template>
      </SplitPanes>
    </div>
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { theme as antTheme } from 'ant-design-vue'
import Header from './layouts/Header.vue'
import SplitPanes from './layouts/SplitPanes.vue'
import LeftPanel from './layouts/LeftPanel.vue'
import Workbench from './layouts/Workbench.vue'
import ChatPanel from './layouts/ChatPanel.vue'
import { useThemeStore } from '@/stores'

const themeStore = useThemeStore()

const theme = computed(() => ({
  algorithm: themeStore.isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
  token: {
    colorPrimary: '#667eea',
    borderRadius: 8,
  },
}))

const handleResize = (leftSize: number, rightSize: number) => {
  console.log('Resize:', leftSize, rightSize)
}
</script>

<style lang="less">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  overflow: hidden;
}

.app-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: background-color 0.3s ease;
}

.app-container:not(.dark-mode) {
  background-color: #f5f5f5;
}

.app-container.dark-mode {
  background-color: #141414;
}

.main-content {
  flex: 1;
  min-height: 0;
}
</style>
