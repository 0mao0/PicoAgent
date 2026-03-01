<template>
  <div class="loading" :class="{ 'loading-fullscreen': fullscreen }">
    <a-spin :size="size" :tip="tip" />
  </div>
</template>

<script setup lang="ts">
import type { SpinProps } from 'ant-design-vue'

withDefaults(defineProps<{
  size?: SpinProps['size']
  tip?: string
  fullscreen?: boolean
}>(), {
  size: 'default',
  fullscreen: false
})
</script>

<style lang="less" scoped>
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;

  &.loading-fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.8);
    z-index: 1000;
  }
}
</style>
