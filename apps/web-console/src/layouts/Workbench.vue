<template>
  <div class="workbench-container">
    <div class="tabs-bar">
      <a-tabs v-model:activeKey="activeTab" type="editable-card" hide-add>
        <a-tab-pane v-for="tab in tabs" :key="tab.key" :closable="tabs.length > 1">
          <template #tab>
            <span>
              <component :is="getIcon(tab.type)" />
              {{ tab.title }}
            </span>
          </template>
        </a-tab-pane>
      </a-tabs>
    </div>
    <div class="content-area">
      <div v-if="tabs.length === 0" class="empty-state">
        <a-empty description="打开文档或项目开始工作" />
      </div>
      <component v-else :is="currentViewer" v-bind="currentTab?.props" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { FileTextOutlined, ApiOutlined, EnvironmentOutlined } from '@ant-design/icons-vue'
import { useWorkbenchStore } from '@/stores/workbench'

const workbenchStore = useWorkbenchStore()

const activeTab = computed({
  get: () => workbenchStore.activeTab,
  set: (val) => workbenchStore.setActiveTab(val)
})

const tabs = computed(() => workbenchStore.tabs)
const currentTab = computed(() => tabs.value.find(t => t.key === activeTab.value))

const currentViewer = computed(() => {
  if (!currentTab.value) return null
  switch (currentTab.value.type) {
    case 'document':
      return 'DocumentViewer'
    case 'sop':
      return 'SOPViewer'
    case 'gis':
      return 'GISViewer'
    default:
      return null
  }
})

const getIcon = (type: string) => {
  switch (type) {
    case 'document':
      return FileTextOutlined
    case 'sop':
      return ApiOutlined
    case 'gis':
      return EnvironmentOutlined
    default:
      return FileTextOutlined
  }
}
</script>

<style lang="less" scoped>
@import '@/styles/variables.less';

.workbench-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  transition: background-color 0.3s;

  :global(html.dark) & {
    background: @dark-background-color-light;
  }
}

.tabs-bar {
  background: #fff;
  border-bottom: 1px solid @border-color-light;
  transition: background-color 0.3s, border-color 0.3s;

  :global(html.dark) & {
    background: @dark-background-color-light;
    border-bottom-color: @dark-border-color-light;
  }

  :deep(.ant-tabs) {
    .ant-tabs-nav {
      margin: 0;
      padding: 0 8px;
    }
  }
}

.content-area {
  flex: 1;
  overflow: hidden;
  background: #f5f5f5;
  transition: background-color 0.3s;

  :global(html.dark) & {
    background: @dark-background-color;
  }
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
