<template>
  <div class="split-pane" ref="containerRef">
    <div
      class="pane pane-left"
      :style="{ width: leftSize + 'px' }"
    >
      <slot name="left" />
    </div>
    <div
      class="splitter"
      @mousedown="startResize"
      :class="{ resizing: isResizing }"
    />
    <div class="pane pane-right">
      <slot name="right" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  initialSize?: number
  minSize?: number
  maxSize?: number
}>(), {
  initialSize: 300,
  minSize: 100,
  maxSize: 600
})

const emit = defineEmits<{
  resize: [size: number]
}>()

const containerRef = ref<HTMLElement | null>(null)
const leftSize = ref(props.initialSize)
const isResizing = ref(false)

const startResize = (e: MouseEvent) => {
  e.preventDefault()
  isResizing.value = true
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
}

const handleResize = (e: MouseEvent) => {
  if (!containerRef.value) return
  
  const containerRect = containerRef.value.getBoundingClientRect()
  let newWidth = e.clientX - containerRect.left
  
  newWidth = Math.max(props.minSize, Math.min(props.maxSize, newWidth))
  leftSize.value = newWidth
  emit('resize', newWidth)
}

const stopResize = () => {
  isResizing.value = false
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
}

onUnmounted(() => {
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<style lang="less" scoped>
.split-pane {
  display: flex;
  height: 100%;
  width: 100%;
}

.pane {
  height: 100%;
  overflow: hidden;
}

.pane-left {
  flex-shrink: 0;
}

.pane-right {
  flex: 1;
  min-width: 0;
}

.splitter {
  width: 4px;
  background: transparent;
  cursor: col-resize;
  flex-shrink: 0;
  transition: background 0.2s;

  &:hover,
  &.resizing {
    background: #1890ff;
  }
}
</style>
