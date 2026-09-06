<template>
  <a-modal
    :open="open"
    title="新增评测"
    :ok-button-props="{ disabled: !canSubmit }"
    :confirm-loading="submitting"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-form layout="vertical" class="eval-run-create">
      <a-form-item label="题集" required>
        <a-select
          v-model:value="form.datasetId"
          :options="datasetOptions"
          :loading="datasetOptionsLoading"
          show-search
          option-filter-prop="label"
          placeholder="选择评测题集"
        />
      </a-form-item>
      <a-form-item label="运行模型">
        <a-select
          v-model:value="form.configName"
          :options="modelOptions"
          :loading="modelsLoading"
          placeholder="默认模型"
        />
      </a-form-item>
      <a-form-item label="评价模型">
        <a-select
          v-model:value="form.judgeConfigName"
          :options="judgeOptions"
          :loading="modelsLoading"
        />
        <div class="eval-run-create__hint">
          判分链：所选模型优先、失败自动回退服务端默认判分链，绝不使用被测模型自判。
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
/** 新增评测弹框：题集默认取左树当前选中，可下拉改；运行/评价模型来自 /api/llm_configs。 */
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'

interface DatasetOption { value: string; label: string }

const props = defineProps<{
  open: boolean
  /** 左树当前选中题集（打开弹框时的默认值） */
  datasetId: string
  datasetOptions: DatasetOption[]
  datasetOptionsLoading?: boolean
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:open': [open: boolean]
  confirm: [payload: { datasetId: string; configName?: string; judgeConfigName?: string }]
}>()

interface LlmConfig { name: string; model: string; configured: boolean }
const models = ref<LlmConfig[]>([])
const modelsLoading = ref(false)

/** 拉取模型配置（默认模型已由后端排首位），失败时下拉为空但不阻塞题集/默认链路 */
const loadModels = async () => {
  if (models.value.length || modelsLoading.value) return
  modelsLoading.value = true
  try {
    const resp = await fetch('/api/llm_configs')
    models.value = resp.ok ? ((await resp.json()) as LlmConfig[]).filter(m => m.configured !== false) : []
    // 首开时 models 尚未到达，回填默认运行模型（仅当前值为空时）
    if (!form.value.configName && models.value.length) {
      form.value.configName = models.value[0].name
    }
  } catch {
    models.value = []
  } finally {
    modelsLoading.value = false
  }
}

const modelOptions = computed(() =>
  models.value.map(m => ({ value: m.name, label: m.name }))
)
/** 评价模型允许留空：空=沿用服务端 EVAL_JUDGE 配置链（历史行为） */
const judgeOptions = computed(() => [
  { value: '', label: '默认（服务端判分链）' },
  ...modelOptions.value,
])

const form = ref<{ datasetId: string; configName: string; judgeConfigName: string }>({
  datasetId: '',
  configName: '',
  judgeConfigName: '',
})

const canSubmit = computed(() => Boolean(form.value.datasetId) && !props.submitting)

watch(() => props.open, (open) => {
  if (!open) return
  void loadModels()
  form.value = {
    datasetId: props.datasetId,
    configName: models.value[0]?.name || '',
    judgeConfigName: '',
  }
})

const handleOk = () => {
  if (!form.value.datasetId) {
    message.warning('请选择题集')
    return
  }
  emit('confirm', {
    datasetId: form.value.datasetId,
    configName: form.value.configName || undefined,
    judgeConfigName: form.value.judgeConfigName || undefined,
  })
}

const handleCancel = () => emit('update:open', false)
</script>

<style lang="less" scoped>
.eval-run-create {
  &__hint {
    margin-top: 6px;
    font-size: 11px;
    line-height: 1.5;
    color: var(--text-secondary);
  }
}
</style>
