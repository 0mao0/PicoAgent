<template>
  <div class="panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-header" @click="handleHeaderClick">
      <span class="panel-title">{{ title }}</span>
      <div class="panel-actions">
        <slot name="actions" />
        <a-button
          v-if="collapsible"
          type="text"
          size="small"
          @click.stop="toggleCollapse"
        >
          <RightOutlined v-if="isCollapsed" />
          <LeftOutlined v-else />
        </a-button>
      </div>
    </div>
    <div class="panel-body" v-show="!isCollapsed">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { LeftOutlined, RightOutlined } from '@ant-design/icons-vue'

const props = withDefaults(defineProps<{
  title?: string
  collapsible?: boolean
  defaultCollapsed?: boolean
}>(), {
  collapsible: true,
  defaultCollapsed: false
})

const emit = defineEmits<{
  collapse: [collapsed: boolean]
}>()

const isCollapsed = ref(props.defaultCollapsed)

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  emit('collapse', isCollapsed.value)
}

const handleHeaderClick = () => {
  if (props.collapsible) {
    toggleCollapse()
  }
}
</script>

<style lang="less" scoped>
.panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;

  &.collapsed {
    .panel-header {
      border-bottom: none;
    }
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
  cursor: pointer;
  user-select: none;

  &:hover {
    background: #fafafa;
  }
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.panel-body {
  flex: 1;
  overflow: hidden;
}
</style>
