<template>
  <div class="error-boundary">
    <slot v-if="!hasError" />
    <a-result v-else status="error" :title="errorTitle" :sub-title="errorMessage">
      <template #extra>
        <a-button type="primary" @click="resetError">重试</a-button>
      </template>
    </a-result>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const props = withDefaults(defineProps<{
  errorTitle?: string
}>(), {
  errorTitle: '发生错误'
})

const hasError = ref(false)
const errorMessage = ref('')

onErrorCaptured((error) => {
  hasError.value = true
  errorMessage.value = error.message
  return false
})

const resetError = () => {
  hasError.value = false
  errorMessage.value = ''
}
</script>

<style lang="less" scoped>
.error-boundary {
  height: 100%;
}
</style>
