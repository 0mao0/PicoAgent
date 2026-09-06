<template>
  <!-- 夜间维护：nightly 门禁结果的历史与明细（数据源 data/evals/nightly/，仅管理员） -->
  <div class="eval-nightly-panel">
    <DataTable
      :columns="columns"
      :data-source="days"
      row-key="date"
      :loading="loading"
      :expand-row-by-click="true"
      :empty-text="EMPTY_TEXT"
      storage-key="angineer-nightly-v2"
      @expand="handleExpand"
    >
      <template #toolbar v-if="latest">
        <div class="nightly-latest">
          <a-space size="middle" wrap>
            <a-tag :color="stateColor(latest.state)">{{ stateLabel(latest.state) }}</a-tag>
            <span class="nightly-metric">{{ fmtTime(latest.generated_at) }}</span>
            <span class="nightly-metric">平均分 <b>{{ pct(latest.overall_score) }}</b></span>
            <span class="nightly-metric">题量 {{ latest.correct ?? '?' }}/{{ latest.total ?? '?' }}</span>
            <span class="nightly-metric">基线 <b>{{ baselinePct(latest) }}</b></span>
            <span class="nightly-metric">Δ <b>{{ deltaText(latest) }}</b></span>
            <span class="nightly-metric">judge 异常 {{ latest.judge_failed_count ?? '—' }}</span>
          </a-space>
          <a-button v-if="latest.run_id" size="small" type="link" @click="emitOpen(latest)">
            在日常测试中打开
          </a-button>
        </div>
      </template>

      <template #headerCell="{ column }">
        <template v-if="column.key === 'delta'">
          基线
          <a-tooltip title="相对固化基线的正确率差（个百分点），+ 表示超过基线；基线为人工钉住的稳定 run">
            <QuestionCircleOutlined class="nightly-help" />
          </a-tooltip>
        </template>
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'time'">
          {{ fmtTime(record.generated_at) }}
        </template>
        <template v-else-if="column.key === 'state'">
          <a-tag :color="stateColor(record.state)">{{ stateLabel(record.state) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'overall'">
          {{ pct(record.overall_score) }}
        </template>
        <template v-else-if="column.key === 'delta'">
          <span :class="deltaClass(record)">{{ deltaText(record) }}</span>
        </template>
        <template v-else-if="column.key === 'verdict'">
          {{ record.verdict || fallbackVerdict(record) }}
        </template>
      </template>

      <template #expandedRowRender="{ record }">
        <a-spin :spinning="!detailOf(record)">
          <NightlyDayDetail v-if="detailOf(record)" :day="record" :detail="detailOf(record)" />
        </a-spin>
      </template>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'
import { DataTable } from '@angineer/table-ui'
import type { DataTableColumn } from '@angineer/table-ui'
import evalsApi from '../../api/evals'
import NightlyDayDetail from './NightlyDayDetail.vue'

interface NightlyDay {
  date: string
  state: string
  generated_at?: string
  overall_score?: number
  correct?: number
  total?: number
  errored?: number
  delta?: number
  delta_ci95?: [number, number]
  base_label?: string
  judge_failed_count?: number
  verdict?: string
  run_id?: string
  dataset_id?: string
  gate_reasons?: string[]
  note?: string
}

interface NightlyDayDetailData {
  nightly?: NightlyDay
  report_md?: string
}

const DEFAULT_NIGHTLY_DATASET = 'open-ragbench-subset-v2'

const emit = defineEmits<{ (e: 'open-run', payload: { datasetId: string; runId: string }): void }>()

const loading = ref(false)
const days = ref<NightlyDay[]>([])
const details = ref<Record<string, NightlyDayDetailData>>({})

const latest = computed(() => days.value[0])

const EMPTY_TEXT = '暂无夜间维护记录 —— nightly 评测流程每晚运行后自动在此发布门禁结论'

const columns: DataTableColumn[] = [
  { title: '序号', key: 'seq', width: 60, minWidth: 50, customRender: ({ index }: { index: number }) => index + 1 },
  { title: '时间', key: 'time', width: 150, minWidth: 120 },
  { title: '结论', key: 'state', width: 80, minWidth: 64 },
  { title: '平均分', key: 'overall', width: 92, minWidth: 80 },
  { title: '题量', key: 'correct', width: 104, minWidth: 88,
    customRender: ({ record }: { record: NightlyDay }) =>
      record.correct != null && record.total != null ? `${record.correct}/${record.total}` : '—' },
  { title: '基线', key: 'delta', width: 90, minWidth: 72 },
  { title: '评价', key: 'verdict', width: 220, minWidth: 160, flex: true, resizable: true },
]

const stateColor = (state: string) =>
  ({ green: 'success', red: 'error', error: 'warning', corrupt: 'default' }[state] || 'default')
const stateLabel = (state: string) =>
  ({ green: '通过', red: '回归', error: '失败', corrupt: '损坏' }[state] || state || '—')
const pct = (value?: number) => (value == null ? '—' : `${(value * 100).toFixed(2)}%`)
const deltaText = (day: NightlyDay) =>
  day.delta == null ? '—' : `${day.delta > 0 ? '+' : ''}${(day.delta * 100).toFixed(2)}`
const deltaClass = (day: NightlyDay) =>
  day.delta == null ? 'nightly-delta--flat' : day.delta > 0 ? 'nightly-delta--up' : day.delta < 0 ? 'nightly-delta--down' : 'nightly-delta--flat'

/** 北京时间、精确到分（generated_at 为 UTC ISO 串） */
const fmtTime = (iso?: string) => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

/** 基线本体分数（基线列展示的是差值，这里给差值的参照物） */
const baselinePct = (day: NightlyDay) =>
  day.overall_score != null && day.delta != null ? pct(day.overall_score - day.delta) : '—'

/** 老数据没有 verdict 字段时按状态兜底生成一句话 */
const fallbackVerdict = (day: NightlyDay) => {
  if (day.state === 'error' || day.state === 'corrupt') return '评测中断，未出结果'
  if (day.state === 'red') return '触发回归门禁，需排查'
  if (day.delta != null && day.delta > 0.005) return '较基线提升，无回归'
  if (day.delta != null && day.delta < -0.005) return '小幅回落，未触门禁'
  return '与基线持平，无回归'
}

const detailOf = (record: NightlyDay): NightlyDayDetailData | undefined => details.value[record.date]

const handleExpand = (expanded: boolean, record: Record<string, any>) => {
  if (expanded) loadDetail((record as NightlyDay).date)
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
.nightly-latest {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  width: 100%;
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid var(--border-color, rgba(5, 5, 5, 0.06));
  border-radius: 8px;
  background: var(--card-bg, var(--bg-primary, #fff));
}
.nightly-metric {
  white-space: nowrap;
}
.nightly-help {
  margin-left: 4px;
  color: var(--text-secondary, rgba(0, 0, 0, 0.45));
}
.nightly-delta--up {
  color: #52c41a;
  font-weight: 600;
}
.nightly-delta--down {
  color: #ff4d4f;
  font-weight: 600;
}
.nightly-delta--flat {
  color: var(--text-secondary, rgba(0, 0, 0, 0.45));
}
</style>
