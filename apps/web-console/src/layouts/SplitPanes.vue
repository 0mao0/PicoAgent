<template>
  <div class="split-pane" ref="containerRef">
    <div class="pane pane-left" :style="{ width: leftSize + 'px' }">
      <slot name="left" />
    </div>
    
    <div class="splitter splitter-left" @mousedown="startLeftResize" :class="{ resizing: isLeftResizing }" />
    
    <div class="pane pane-center">
      <slot name="center" />
    </div>
    
    <div class="splitter splitter-right" @mousedown="startRightResize" :class="{ resizing: isRightResizing }" />
    
    <div class="pane pane-right" :style="{ width: rightSize + 'px' }">
      <slot name="right" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  leftMin?: number
  leftMax?: number
  rightMin?: number
  rightMax?: number
  initialLeftRatio?: number
  initialRightRatio?: number
}>(), {
  leftMin: 200,
  leftMax: 600,
  rightMin: 200,
  rightMax: 600,
  initialLeftRatio: 0.2,
  initialRightRatio: 0.2
})

const emit = defineEmits<{
  resize: [leftSize: number, rightSize: number]
}>()

const containerRef = ref<HTMLElement | null>(null)
const leftSize = ref(300)
const rightSize = ref(380)
const isLeftResizing = ref(false)
const isRightResizing = ref(false)

const onLeftResize = (e: MouseEvent) => {
  if (!containerRef.value) return
  
  const containerRect = containerRef.value.getBoundingClientRect()
  let newWidth = e.clientX - containerRect.left
  
  newWidth = Math.max(props.leftMin, Math.min(props.leftMax, newWidth))
  leftSize.value = newWidth
  emit('resize', leftSize.value, rightSize.value)
}

const startLeftResize = (e: MouseEvent) => {
  e.preventDefault()
  isLeftResizing.value = true
  document.addEventListener('mousemove', onLeftResize)
  document.addEventListener('mouseup', stopLeftResize)
}

const stopLeftResize = () => {
  isLeftResizing.value = false
  document.removeEventListener('mousemove', onLeftResize)
  document.removeEventListener('mouseup', stopLeftResize)
}

const onRightResize = (e: MouseEvent) => {
  if (!containerRef.value) return
  
  const containerRect = containerRef.value.getBoundingClientRect()
  let newWidth = containerRect.right - e.clientX
  
  newWidth = Math.max(props.rightMin, Math.min(props.rightMax, newWidth))
  rightSize.value = newWidth
  emit('resize', leftSize.value, rightSize.value)
}

const startRightResize = (e: MouseEvent) => {
  e.preventDefault()
  isRightResizing.value = true
  document.addEventListener('mousemove', onRightResize)
  document.addEventListener('mouseup', stopRightResize)
}

const stopRightResize = () => {
  isRightResizing.value = false
  document.removeEventListener('mousemove', onRightResize)
  document.removeEventListener('mouseup', stopRightResize)
}

const initSizes = () => {
  if (!containerRef.value) return
  
  const containerWidth = containerRef.value.offsetWidth
  leftSize.value = Math.max(props.leftMin, Math.min(props.leftMax, containerWidth * props.initialLeftRatio))
  rightSize.value = Math.max(props.rightMin, Math.min(props.rightMax, containerWidth * props.initialRightRatio))
}

onMounted(() => {
  initSizes()
  window.addEventListener('resize', initSizes)
})

onUnmounted(() => {
  window.removeEventListener('resize', initSizes)
  document.removeEventListener('mousemove', onLeftResize)
  document.removeEventListener('mouseup', stopLeftResize)
  document.removeEventListener('mousemove', onRightResize)
  document.removeEventListener('mouseup', stopRightResize)
})
</script>

<style lang="less" scoped>
.split-pane {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.pane {
  height: 100%;
  overflow: hidden;
}

.pane-left,
.pane-right {
  flex-shrink: 0;
}

.pane-center {
  flex: 1;
  min-width: 0;
}

.splitter {
  width: 4px;
  background: transparent;
  cursor: col-resize;
  flex-shrink: 0;
  transition: background 0.2s;
  position: relative;

  &:hover,
  &.resizing {
    background: #1890ff;
  }

  &::before {
    content: '';
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 2px;
    height: 40px;
    background: rgba(0, 0, 0, 0.1);
    border-radius: 1px;
  }
}
</style>
