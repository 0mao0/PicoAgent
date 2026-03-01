<template>
  <div class="app-layout" :class="{ 'dark-mode': isDark }">
    <div class="layout-header" v-if="$slots.header">
      <slot name="header" />
    </div>
    <div class="layout-body">
      <div
        class="layout-left"
        :style="{ width: leftWidth + 'px' }"
        v-show="showLeft"
      >
        <slot name="left" />
      </div>
      <div class="layout-center">
        <slot />
      </div>
      <div
        class="layout-right"
        :style="{ width: rightWidth + 'px' }"
        v-show="showRight"
      >
        <slot name="right" />
      </div>
    </div>
    <div class="layout-footer" v-if="$slots.footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  leftWidth?: number
  rightWidth?: number
  showLeft?: boolean
  showRight?: boolean
  darkMode?: boolean
}>(), {
  leftWidth: 280,
  rightWidth: 380,
  showLeft: true,
  showRight: true,
  darkMode: false
})

const isDark = computed(() => props.darkMode)
</script>

<style lang="less" scoped>
.app-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;

  &.dark-mode {
    background: #1f1f1f;
    color: #fff;
  }
}

.layout-header {
  height: 48px;
  flex-shrink: 0;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.layout-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.layout-left {
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e8e8e8;
}

.layout-center {
  flex: 1;
  min-width: 0;
  background: #fff;
}

.layout-right {
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid #e8e8e8;
}

.layout-footer {
  height: 32px;
  flex-shrink: 0;
  background: #fff;
  border-top: 1px solid #e8e8e8;
}
</style>
