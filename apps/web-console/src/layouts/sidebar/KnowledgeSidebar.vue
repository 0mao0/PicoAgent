<template>
  <div class="knowledge-sidebar">
    <div class="search-box">
      <a-input-search v-model:value="searchText" placeholder="搜索知识库..." />
    </div>
    <div class="library-tree">
      <a-tree
        :tree-data="treeData"
        :expanded-keys="expandedKeys"
        :selected-keys="selectedKeys"
        @expand="onExpand"
        @select="onSelect"
      >
        <template #title="{ title, icon, isDoc }">
          <span>
            <component :is="icon" v-if="icon" style="margin-right: 4px" />
            {{ title }}
          </span>
        </template>
      </a-tree>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { BookOutlined, FileTextOutlined, FolderOutlined } from '@ant-design/icons-vue'
import { useWorkbenchStore } from '@/stores/workbench'

const workbenchStore = useWorkbenchStore()
const searchText = ref('')
const expandedKeys = ref<string[]>(['kb-1'])
const selectedKeys = ref<string[]>([])

const treeData = ref([
  {
    key: 'kb-1',
    title: '海港总体设计规范',
    icon: BookOutlined,
    children: [
      {
        key: 'kb-1-ch1',
        title: '1 总则',
        icon: FileTextOutlined,
        isDoc: true
      },
      {
        key: 'kb-1-ch2',
        title: '2 术语',
        icon: FileTextOutlined,
        isDoc: true
      },
      {
        key: 'kb-1-ch3',
        title: '3 港址选择',
        icon: FileTextOutlined,
        isDoc: true
      },
      {
        key: 'kb-1-ch4',
        title: '4 设计基础条件',
        icon: FileTextOutlined,
        isDoc: true
      },
      {
        key: 'kb-1-ch5',
        title: '5 港口平面',
        icon: FileTextOutlined,
        isDoc: true
      },
      {
        key: 'kb-1-ch6',
        title: '6 进港航道、锚地',
        icon: FileTextOutlined,
        isDoc: true
      }
    ]
  },
  {
    key: 'kb-2',
    title: '港口工程荷载规范',
    icon: BookOutlined,
    children: []
  }
])

const onExpand = (keys: string[]) => {
  expandedKeys.value = keys
}

const onSelect = (keys: string[], info: any) => {
  selectedKeys.value = keys
  if (info.node.isDoc) {
    workbenchStore.openTab({
      key: keys[0],
      type: 'document',
      title: info.node.title,
      props: { docId: keys[0] }
    })
  }
}
</script>

<style lang="less" scoped>
.knowledge-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.search-box {
  padding: 12px;
}

.library-tree {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}
</style>
