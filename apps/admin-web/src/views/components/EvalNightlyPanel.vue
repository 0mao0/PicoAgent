<template>
  <!-- 夜间维护：nightly 门禁结果的历史与明细（数据源 data/evals/nightly/，仅管理员） -->
  <div class="eval-nightly-panel">
    <div class="nightly-schedule">
      <div class="nightly-schedule__group">
        <span class="nightly-schedule__label">每晚定时执行（北京时间）</span>
        <a-switch v-model:checked="sched.enabled" size="small" />
        <a-time-picker
          v-model:value="sched.time"
          format="HH:mm"
          value-format="HH:mm"
          :allow-clear="false"
          size="small"
          width="88px"
        />
        <template v-if="scheduleDirty">
          <a-button size="small" type="primary" :loading="sched.saving" @click="saveSchedule">
            保存
          </a-button>
          <a-button size="small" @click="cancelSchedule">取消</a-button>
        </template>
      </div>
      <a-button size="small" :disabled="sched.running" @click="openRunModal">
        {{ sched.running ? '流水线运行中…' : '立即运行' }}
      </a-button>
    </div>
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
      <template #headerCell="{ column }">
        <template v-if="column.key === 'delta'">
          基线
          <a-tooltip title="相对固化基线的正确率差（个百分点），+ 表示超过基线；基线为人工钉住的稳定 run">
            <QuestionCircleOutlined class="nightly-help" />
          </a-tooltip>
        </template>
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'subject'">
          {{ record.subject || record.dataset_id || '—' }}
        </template>
        <template v-else-if="column.key === 'time'">
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
          <NightlyDayDetail
            v-if="detailOf(record)"
            :day="record"
            :detail="detailOf(record)"
            @open-run="(p) => emit('open-run', p)"
          />
        </a-spin>
      </template>
    </DataTable>

    <a-modal
      v-model:open="runModal.open"
      title="本次夜间流水线将执行"
      ok-text="开始运行"
      cancel-text="关闭"
      :confirm-loading="runModal.launching"
      @ok="confirmLaunch"
    >
      <a-spin :spinning="runModal.loading">
        <a-descriptions v-if="runModal.plan" size="small" :column="1" bordered>
          <a-descriptions-item label="测试集">
            {{ runModal.plan.dataset?.title }}（{{ runModal.plan.dataset?.question_count ?? '?' }} 题）
          </a-descriptions-item>
          <a-descriptions-item label="作答模型">{{ runModal.plan.answer_model }}</a-descriptions-item>
          <a-descriptions-item label="评判模型（候选链）">
            {{ (runModal.plan.judge_models || []).join(' → ') }}
          </a-descriptions-item>
          <a-descriptions-item label="并发 / 单次时限">
            {{ runModal.plan.concurrency }} · {{ runModal.plan.timeout_minutes }} 分钟
          </a-descriptions-item>
          <a-descriptions-item label="异常自动补判">
            最多 {{ runModal.plan.retry_rounds }} 轮（judge 抖动仅重判分，执行错误整题重跑）
          </a-descriptions-item>
          <a-descriptions-item label="结果去向">
            本页新增当日结论条目 + 企微通知（评测逐题结果进「日常测试」历史）
          </a-descriptions-item>
        </a-descriptions>
        <a-empty v-else-if="!runModal.loading" description="执行计划读取失败" />
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'
import { DataTable } from '@angineer/table-ui'
import type { DataTableColumn } from '@angineer/table-ui'
import evalsApi from '../../api/evals'
import NightlyDayDetail from './NightlyDayDetail.vue'

interface NightlyDay {
  date: string
  state: string
  subject?: string
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

const emit = defineEmits<{ (e: 'open-run', payload: { datasetId: string; runId: string }): void }>()

const loading = ref(false)
const days = ref<NightlyDay[]>([])
const details = ref<Record<string, NightlyDayDetailData>>({})

const EMPTY_TEXT = '暂无夜间维护记录 —— nightly 评测流程每晚运行后自动在此发布门禁结论'

const columns: DataTableColumn[] = [
  { title: '序号', key: 'seq', width: 60, minWidth: 50, customRender: ({ index }: { index: number }) => index + 1 },
  { title: '维护内容', key: 'subject', width: 240, minWidth: 150, ellipsis: true },
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

/** 老数据没有 verdict 字段时按状态兜底生成一句话（措辞与发布端 _verdict 同风格，面向普通读者） */
const fallbackVerdict = (day: NightlyDay) => {
  if (day.state === 'error' || day.state === 'corrupt') return '评测中断，未出结果'
  if (day.state === 'red') return '整体变差，需排查'
  if (day.delta != null && day.delta > 0.005) return '较基线提升，没有题目变差'
  if (day.delta != null && day.delta < -0.005) return '小幅回落，正常波动'
  return '与基线持平，没有变差'
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

// ── 定时调度设置（存服务器 data/evals/nightly_settings.json，1 分钟内生效）──
// 交互约定：默认只读展示"开关+时间"，改动后才出现 保存/取消；历史看下方列表，工具条不复述。
interface NightlySettingsRsp {
  enabled: boolean
  hour: number
  minute: number
  running?: boolean
  next_fire_at?: string | null
}
interface NightlyRunPlan {
  dataset?: { id: string; title: string; question_count?: number }
  answer_model?: string
  judge_models?: string[]
  concurrency?: number
  timeout_minutes?: number
  retry_rounds?: number
}

const sched = reactive({
  enabled: false,
  time: '01:00',
  saving: false,
  running: false,
  savedEnabled: false,
  savedTime: '01:00',
})

const scheduleDirty = computed(() => sched.enabled !== sched.savedEnabled || sched.time !== sched.savedTime)

const runModal = reactive({
  open: false,
  loading: false,
  launching: false,
  plan: null as NightlyRunPlan | null,
})

let runPollTimer: ReturnType<typeof setInterval> | undefined

const loadSchedule = async () => {
  try {
    const s = await evalsApi.getNightlySettings() as NightlySettingsRsp
    const time = `${String(s.hour ?? 1).padStart(2, '0')}:${String(s.minute ?? 0).padStart(2, '0')}`
    if (!scheduleDirty.value) {
      // 用户没在编辑时才覆盖编辑区，避免轮询冲掉未保存的修改
      sched.enabled = sched.savedEnabled = !!s.enabled
      sched.time = sched.savedTime = time
    }
    sched.running = !!s.running
    if (s.running && !runPollTimer) startRunPolling()
    if (!s.running && runPollTimer) stopRunPolling()
  } catch {
    // 读取失败保持默认值展示，不打扰主列表
  }
}

/** 流水线运行期间每分钟刷状态；结束后自动刷新结论列表（当天新条目即时可见） */
const startRunPolling = () => {
  runPollTimer = setInterval(async () => {
    await loadSchedule()
    if (!sched.running) {
      stopRunPolling()
      fetchList()
    }
  }, 60_000)
}
const stopRunPolling = () => {
  if (runPollTimer) clearInterval(runPollTimer)
  runPollTimer = undefined
}

const saveSchedule = async () => {
  sched.saving = true
  try {
    const [hour, minute] = sched.time.split(':').map(Number)
    const s = await evalsApi.saveNightlySettings({ enabled: sched.enabled, hour, minute }) as NightlySettingsRsp
    sched.savedEnabled = !!s.enabled
    sched.savedTime = `${String(s.hour ?? 1).padStart(2, '0')}:${String(s.minute ?? 0).padStart(2, '0')}`
    message.success(sched.enabled ? `已保存：每晚 ${sched.savedTime} 执行` : '已保存：定时执行关闭')
  } catch (e) {
    message.error(String((e as Error)?.message || '保存失败'))
  } finally {
    sched.saving = false
  }
}

const cancelSchedule = () => {
  sched.enabled = sched.savedEnabled
  sched.time = sched.savedTime
}

const openRunModal = async () => {
  runModal.open = true
  runModal.loading = true
  try {
    runModal.plan = await evalsApi.getNightlyRunPlan() as NightlyRunPlan
  } catch {
    runModal.plan = null
  } finally {
    runModal.loading = false
  }
}

const confirmLaunch = async () => {
  runModal.launching = true
  try {
    const r = await evalsApi.runNightlyNow() as { ok: boolean; detail?: string }
    if (r.ok) {
      message.success('夜间流水线已启动：完成前本页将显示运行状态，结束后自动刷新结论并推企微通知')
      runModal.open = false
      sched.running = true
      startRunPolling()
    } else {
      message.warning(r.detail || '未能启动')
    }
  } catch (e) {
    message.error(String((e as Error)?.message || '启动失败'))
  } finally {
    runModal.launching = false
  }
}

onMounted(() => {
  fetchList()
  loadSchedule()
})
onBeforeUnmount(stopRunPolling)
</script>

<style scoped>
.eval-nightly-panel {
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding: 16px 24px;
  box-sizing: border-box;
}
/* 工具条式布局（对齐知识库列表页的留白）：状态信息居左、操作靠右，与表格拉开呼吸间距 */
.nightly-schedule {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  min-height: 32px;
  margin-bottom: 20px;
}
/* 左组自排 flex 垂直居中（a-space 的行盒基线会把不同高度控件排歪，实测中心差 4px） */
.nightly-schedule__group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.nightly-schedule__label,
.nightly-schedule__status {
  font-size: 12px;
  color: var(--text-secondary, rgba(0, 0, 0, 0.45));
}
.nightly-schedule__status {
  margin-right: auto;
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
