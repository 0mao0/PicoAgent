<template>
  <span class="icon-font" @click="handleClick">
    <component :is="icon" v-if="icon" />
    <slot v-else />
  </span>
</template>

<script setup lang="ts">
defineProps<{
  icon?: any
  type?: string
}>()

const emit = defineEmits<{
  click: []
}>()

const handleClick = () => {
  emit('click')
}
</script>

<style lang="less" scoped>
.icon-font {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: inherit;
  color: inherit;
}
</style>
