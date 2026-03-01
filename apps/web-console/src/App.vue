<template>
  <a-config-provider :locale="zhCN">
    <div class="app-container">
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
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import Header from './layouts/Header.vue'
import SplitPanes from './layouts/SplitPanes.vue'
import LeftPanel from './layouts/LeftPanel.vue'
import Workbench from './layouts/Workbench.vue'
import ChatPanel from './layouts/ChatPanel.vue'

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
  background-color: #1f1f1f;
}

.main-content {
  flex: 1;
  min-height: 0;
}
</style>
