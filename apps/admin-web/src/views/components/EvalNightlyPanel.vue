<template>
  <!-- 夜间维护：nightly 门禁结果的历史与明细（数据源 data/evals/nightly/，仅管理员） -->
  <div class="eval-nightly-panel">
    <a-spin :spinning="loading">
      <a-empty
        v-if="!loading && !days.length"
        class="nightly-empty"
        description="暂无夜间维护记录 —— nightly 评测流程每晚运行后自动在此发布门禁结论"
      />
      <template v-else>
        <a-card v-if="latest" size="small" class="nightly-latest">
          <div class="nightly-latest__row">
            <a-space size="middle" wrap>
              <a-tag :color="stateColor(latest.state)">{{ stateLabel(latest.state) }}</a-tag>
              <span class="nightly-metric">最新 {{ latest.date }}</span>
              <span class="nightly-metric">Overall <b>{{ pct(latest.overall_score) }}</b></span>
              <span class="nightly-metric">正确 {{ latest.correct ?? '?' }}/{{ latest.total ?? '?' }}</span>
              <span class="nightly-metric">Δ 基线 <b>{{ deltaText(latest) }}</b></span>
              <span class="nightly-metric">judge 异常 {{ latest.judge_failed_count ?? '—' }}</span>
            </a-space>
            <a-button v-if="latest.run_id" size="small" type="link" @click="emitOpen(latest)">
              在日常测试中打开
            </a-button>
          </div>
        </a-card>

        <a-table
          class="nightly-table"
          :data-source="days"
          :columns="columns"
          row-key="date"
          size="small"
          :pagination="false"
          @expand="(expanded: boolean, record: NightlyDay) => expanded && loadDetail(record.date)"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'state'">
              <a-tag :color="stateColor(record.state)">{{ stateLabel(record.state) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'overall'">
              {{ pct(record.overall_score) }}
            </template>
            <template v-else-if="column.key === 'delta'">
              {{ deltaText(record) }}
            </template>
          </template>
          <template #expandedRowRender="{ record }">
            <a-spin :spinning="!detailOf(record)">
              <div v-if="detailOf(record)" class="nightly-detail">
                <a-alert
                  v-for="(reason, idx) in detailOf(record)?.nightly?.gate_reasons || []"
                  :key="idx"
                  type="error"
                  :message="reason"
                  show-icon
                  class="nightly-reason"
                />
                <a-alert
                  v-if="detailOf(record)?.nightly?.note"
                  type="warning"
                  :message="`执行记录：${detailOf(record)?.nightly?.note}`"
                  show-icon
                  class="nightly-reason"
                />
                <a-descriptions v-if="matrixOf(record)" size="small" bordered :column="4" class="nightly-matrix">
                  <a-descriptions-item label="双过">{{ matrixOf(record)?.pp }}</a-descriptions-item>
                  <a-descriptions-item label="新修复">{{ matrixOf(record)?.pf }}</a-descriptions-item>
                  <a-descriptions-item label="新回退">{{ matrixOf(record)?.fp }}</a-descriptions-item>
                  <a-descriptions-item label="双挂">{{ matrixOf(record)?.ff }}</a-descriptions-item>
                </a-descriptions>
                <div v-if="regressionRows(record).length" class="nightly-regressions">
                  <div class="nightly-block-title">回退归因（旧过新挂）</div>
                  <a-table
                    :data-source="regressionRows(record)"
                    :columns="regressionColumns"
                    row-key="qid"
                    size="small"
                    :pagination="false"
                  />
                </div>
                <a-collapse v-if="detailOf(record)?.report_md" class="nightly-report">
                  <a-collapse-panel key="report" header="评测报告（report.md）">
                    <pre class="nightly-report__raw">{{ detailOf(record)?.report_md }}</pre>
                  </a-collapse-panel>
                </a-collapse>
              </div>
            </a-spin>
          </template>
        </a-table>
      </template>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import evalsApi from '../../api/evals'

interface NightlyMatrix {
  pp?: number
  pf?: number
  fp?: number
  ff?: number
}

interface NightlyDay {
  date: string
  state: string
  overall_score?: number
  correct?: number
  total?: number
  errored?: number
  delta?: number
  delta_ci95?: [number, number]
  base_label?: string
  judge_failed_count?: number
  matrix?: NightlyMatrix
  run_id?: string
  dataset_id?: string
  gate_reasons?: string[]
  regressions?: Record<string, string>
  note?: string
}

interface NightlyDayDetail {
  nightly?: NightlyDay
  report_md?: string
}

const DEFAULT_NIGHTLY_DATASET = 'open-ragbench-subset-v2'

const emit = defineEmits<{ (e: 'open-run', payload: { datasetId: string; runId: string }): void }>()

const loading = ref(false)
const days = ref<NightlyDay[]>([])
const details = ref<Record<string, NightlyDayDetail>>({})

const latest = computed(() => days.value[0])

const columns = [
  { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
  { title: '结论', dataIndex: 'state', key: 'state', width: 90 },
  { title: 'Overall', key: 'overall', width: 90 },
  { title: '正确', key: 'correct', width: 100,
    customRender: ({ record }: { record: NightlyDay }) =>
      record.correct != null && record.total != null ? `${record.correct}/${record.total}` : '—' },
  { title: 'Δ 基线', key: 'delta', width: 100 },
  { title: '基线', dataIndex: 'base_label', key: 'base_label', ellipsis: true },
]

const regressionColumns = [
  { title: '题目', dataIndex: 'qid', key: 'qid', width: 140 },
  { title: '归因', dataIndex: 'bucket', key: 'bucket' },
]

const stateColor = (state: string) =>
  ({ green: 'success', red: 'error', error: 'warning', corrupt: 'default' }[state] || 'default')
const stateLabel = (state: string) =>
  ({ green: '通过', red: '回归', error: '失败', corrupt: '损坏' }[state] || state || '—')
const pct = (value?: number) => (value == null ? '—' : `${(value * 100).toFixed(2)}%`)
const deltaText = (day: NightlyDay) =>
  day.delta == null ? '—' : `${(day.delta * 100).toFixed(2)}pp`

const detailOf = (record: NightlyDay): NightlyDayDetail | undefined => details.value[record.date]

const matrixOf = (record: NightlyDay): NightlyMatrix | undefined =>
  detailOf(record)?.nightly?.matrix || record.matrix

const regressionRows = (record: NightlyDay) => {
  const map = detailOf(record)?.nightly?.regressions || record.regressions || {}
  return Object.entries(map).slice(0, 50).map(([qid, bucket]) => ({ qid: qid.slice(0, 8), bucket }))
}

const loadDetail = async (date: string) => {
  if (details.value[date]) return
  try {
    details.value[date] = await evalsApi.getNightlyDay(date)
  } catch (e) {
    details.value[date] = { nightly: { date, state: 'corrupt', note: String((e as Error).message || '读取失败') } }
  }
}

const emitOpen = (day: NightlyDay) => {
  if (!day.run_id) return
  emit('open-run', { datasetId: day.dataset_id || DEFAULT_NIGHTLY_DATASET, runId: day.run_id })
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await evalsApi.getNightlyList()
    days.value = (res as { days: NightlyDay[] }).days || []
  } catch (e) {
    console.error('[nightly] 列表加载失败', e)
    message.error('夜间维护记录加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchList)
</script>

<style scoped>
.eval-nightly-panel {
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding: 12px 16px;
  box-sizing: border-box;
}
.nightly-empty {
  margin-top: 15vh;
}
.nightly-latest {
  margin-bottom: 12px;
}
.nightly-latest__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.nightly-metric {
  white-space: nowrap;
}
.nightly-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.nightly-reason {
  margin: 0;
}
.nightly-block-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.nightly-report__raw {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 18px;
  max-height: 360px;
  overflow: auto;
}
</style>
