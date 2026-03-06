<template>
  <div class="workbench-container" :class="{ 'dark-mode': themeStore.isDark }">
    <div class="tabs-bar">
      <a-tabs v-model:activeKey="activeTab" type="editable-card" hide-add @edit="handleTabEdit">
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
import type { WorkbenchTabType } from '@angineer/docs-ui'
import { useWorkbenchStore } from '@/stores/workbench'
import { useThemeStore } from '@/stores'
import DocumentView from '@/views/DocumentView.vue'
import SOPView from '@/views/SOPView.vue'
import GISView from '@/views/GISView.vue'
import ProjectView from '@/views/ProjectView.vue'

const workbenchStore = useWorkbenchStore()
const themeStore = useThemeStore()

const activeTab = computed({
  get: () => workbenchStore.activeTab,
  set: (val) => workbenchStore.setActiveTab(val)
})

const tabs = computed(() => workbenchStore.tabs)
const currentTab = computed(() => tabs.value.find(t => t.key === activeTab.value))
const viewerMap: Record<WorkbenchTabType, unknown> = {
  document: DocumentView,
  sop: SOPView,
  gis: GISView,
  code: DocumentView,
  project: ProjectView
}

const currentViewer = computed(() => {
  if (!currentTab.value) return null
  return viewerMap[currentTab.value.type] || null
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

const handleTabEdit = (targetKey: string | MouseEvent | KeyboardEvent, action: 'add' | 'remove') => {
  if (action !== 'remove' || typeof targetKey !== 'string') {
    return
  }
  workbenchStore.closeTab(targetKey)
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
}

.workbench-container:not(.dark-mode) {
  .tabs-bar {
    background: #fff;
    border-bottom: 1px solid @border-color-light;
  }
  
  .content-area {
    background: #f5f5f5;
  }
}

.workbench-container.dark-mode {
  .tabs-bar {
    background: #1f1f1f;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  
  .content-area {
    background: #141414;
  }
}

.tabs-bar {
  transition: background-color 0.3s, border-color 0.3s;

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
  transition: background-color 0.3s;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
