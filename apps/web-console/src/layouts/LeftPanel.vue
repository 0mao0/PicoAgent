<template>
  <div class="left-panel-container">
    <a-tabs v-model:activeKey="activeTab" class="resource-tabs">
      <a-tab-pane key="knowledge" tab="知识库">
        <div class="knowledge-panel">
          <SearchBox 
            @search="onSearch" 
            @select="onSelectResult"
          />
          <KnowledgeTree @select="onSelectDoc" />
        </div>
      </a-tab-pane>
      <a-tab-pane key="sop" tab="SOP">
        <SOPSidebar />
      </a-tab-pane>
      <a-tab-pane key="project" tab="项目">
        <ProjectSidebar />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { KnowledgeTree, SearchBox } from '@angineer/docs-ui'
import SOPSidebar from './sidebar/SOPSidebar.vue'
import ProjectSidebar from './sidebar/ProjectSidebar.vue'

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
  background: #fff;
  border-right: 1px solid @border-color-light;
  transition: background-color 0.3s, border-color 0.3s;

  :global(html.dark) & {
    background: @dark-background-color-light;
    border-right-color: @dark-border-color-light;
  }

  .resource-tabs {
    height: 100%;
    display: flex;
    flex-direction: column;

    :deep(.ant-tabs-nav) {
      margin: 0;
      padding: 0 12px;
      background: #fafafa;
      flex-shrink: 0;
      transition: background-color 0.3s;
    }

    :global(html.dark) & :deep(.ant-tabs-nav) {
      background: @dark-border-color-light;
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
}

.knowledge-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 12px;
}
</style>
