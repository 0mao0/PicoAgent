<template>
  <div class="left-panel-container" :class="{ 'dark-mode': themeStore.isDark }">
    <a-tabs v-model:activeKey="activeTab" class="resource-tabs">
      <a-tab-pane key="project" tab="项目">
        <ProjectSidebar />
      </a-tab-pane>
      <a-tab-pane key="knowledge" tab="知识">
        <div class="knowledge-panel">
          <SearchBox 
            @search="onSearch" 
            @select="onSelectResult"
          />
          <KnowledgeTree @select="onSelectDoc" />
        </div>
      </a-tab-pane>
      <a-tab-pane key="sop" tab="经验">
        <SOPSidebar />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { KnowledgeTree, SearchBox } from '@angineer/docs-ui'
import SOPSidebar from './sidebar/SOPSidebar.vue'
import ProjectSidebar from './sidebar/ProjectSidebar.vue'
import { useThemeStore } from '@/stores'

const themeStore = useThemeStore()
const activeTab = ref('knowledge')

const onSearch = (query: string) => {
  console.log('Search:', query)
}

const onSelectResult = (result: any) => {
  console.log('Select result:', result)
}

const onSelectDoc = (node: any) => {
  console.log('Select doc:', node)
}
</script>

<style lang="less" scoped>
@import '@/styles/variables.less';

.left-panel-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
}

.left-panel-container:not(.dark-mode) {
  background: #ffffff;
  border-right: 1px solid rgba(0, 0, 0, 0.06);
}

.left-panel-container.dark-mode {
  background: #1f1f1f;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.resource-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;

  :deep(.ant-tabs-nav) {
    margin: 0;
    padding: 0 16px;
    flex-shrink: 0;
    transition: background-color 0.3s ease;
  }

  .left-panel-container:not(.dark-mode) & :deep(.ant-tabs-nav) {
    background: rgba(0, 0, 0, 0.02);
  }

  .left-panel-container.dark-mode & :deep(.ant-tabs-nav) {
    background: rgba(255, 255, 255, 0.03);
  }

  :deep(.ant-tabs-content-holder) {
    flex: 1;
    overflow: hidden;
  }

  :deep(.ant-tabs-content) {
    height: 100%;
  }

  :deep(.ant-tabs-tabpane) {
    height: 100%;
    overflow-y: auto;
  }
}

.knowledge-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 8px;
  overflow: hidden;
}
</style>
