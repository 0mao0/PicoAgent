<template>
  <div class="sop-sidebar">
    <div class="sop-list">
      <a-list :data-source="sopList" size="small">
        <template #renderItem="{ item }">
          <a-list-item @click="openSOP(item)">
            <a-list-item-meta :title="item.title" :description="item.description">
              <template #avatar>
                <a-avatar :style="{ backgroundColor: '#1890ff' }">
                  <template #icon><ApiOutlined /></template>
                </a-avatar>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ApiOutlined } from '@ant-design/icons-vue'
import { useWorkbenchStore } from '@/stores/workbench'

const workbenchStore = useWorkbenchStore()

const sopList = ref([
  { id: 'sop-1', title: '航道设计流程', description: '进港航道设计标准流程' },
  { id: 'sop-2', title: '码头选址评估', description: '港址选择与评估流程' },
  { id: 'sop-3', title: '泊位通过能力计算', description: '泊位设计通过能力计算流程' }
])

const openSOP = (sop: any) => {
  workbenchStore.openTab({
    key: sop.id,
    type: 'sop',
    title: sop.title,
    props: { sopId: sop.id }
  })
}
</script>

<style lang="less" scoped>
.sop-sidebar {
  height: 100%;
  padding: 12px;
}

.sop-list {
  :deep(.ant-list-item) {
    cursor: pointer;
    &:hover {
      background: #f5f5f5;
    }
  }
}
</style>
