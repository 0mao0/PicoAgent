<template>
  <!-- 夜间维护单日明细：总览（矩阵图+分行结论）+ 三个折叠条（回退题/新修复题/评测报告） -->
  <div class="ndd">
    <div class="ndd-overview">
      <div class="ndd-overview__left">
        <div class="ndd-chips">
          <span v-for="chip in chips" :key="chip.label" class="ndd-chip">
            <i class="ndd-dot" :style="{ background: chip.color }" />{{ chip.label }}
            <b>{{ chip.value ?? '—' }}</b>
          </span>
        </div>
        <div v-if="hasMatrix" ref="donutEl" class="ndd-donut" />
      </div>
      <div class="ndd-analysis">
        <p v-for="(line, i) in analysisLines" :key="i" class="ndd-analysis__line">{{ line }}</p>
        <a-button
          v-if="cur.run_id"
          class="ndd-open-run"
          size="small"
          type="link"
          @click="$emit('open-run', { datasetId: cur.dataset_id || DEFAULT_NIGHTLY_DATASET, runId: cur.run_id })"
        >
          在日常测试中打开本次运行
        </a-button>
        <a-alert
          v-for="(reason, i) in cur.gate_reasons || []"
          :key="`r${i}`"
          type="error"
          :message="reason"
          show-icon
          class="ndd-alert"
        />
        <a-alert
          v-if="cur.note"
          type="warning"
          :message="`执行记录：${cur.note}`"
          show-icon
          class="ndd-alert"
        />
      </div>
    </div>

    <a-collapse class="ndd-collapses">
      <a-collapse-panel key="regressions" :header="`回退题目（昨晚答对 → 今晚答错，${regressions.length} 题）`">
        <a-empty
          v-if="!regressions.length"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          description="没有题目从答对变成答错"
        />
        <ul v-else class="ndd-qlist">
          <li v-for="item in regressions" :key="item.qid" class="ndd-qitem">
            <div class="ndd-qitem__head">
              <a-tooltip :title="item.bucket_detail || undefined">
                <a-tag :color="bucketColor(item.bucket)">{{ bucketPlain(item.bucket) }}</a-tag>
              </a-tooltip>
              <span class="ndd-qitem__mark">昨晚 ✓ → 今晚 ✗</span>
            </div>
            <a-tooltip :title="item.question || undefined">
              <p class="ndd-qitem__q">{{ item.question || `题目 ${item.qid.slice(0, 8)}` }}</p>
            </a-tooltip>
          </li>
        </ul>
      </a-collapse-panel>

      <a-collapse-panel key="fixed" :header="fixedHeader">
        <ul class="ndd-qlist">
          <li v-for="item in fixed" :key="item.qid" class="ndd-qitem ndd-qitem--fixed">
            <div class="ndd-qitem__head">
              <a-tag color="success">已修复</a-tag>
              <span class="ndd-qitem__mark">昨晚 ✗ → 今晚 ✓</span>
            </div>
            <a-tooltip :title="item.question || undefined">
              <p class="ndd-qitem__q">{{ item.question || `题目 ${item.qid.slice(0, 8)}` }}</p>
            </a-tooltip>
          </li>
        </ul>
      </a-collapse-panel>

      <a-collapse-panel v-if="detail?.report_md" key="report" header="评测报告（report.md）">
        <pre class="ndd-report__raw">{{ detail?.report_md }}</pre>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Empty } from 'ant-design-vue'
import * as echarts from 'echarts'

interface QuestionItem {
  qid: string
  question?: string
  bucket?: string
  bucket_detail?: string
}

interface NightlyMatrix { pp?: number; pf?: number; fp?: number; ff?: number }

interface NightlyDayLite {
  date: string
  state: string
  overall_score?: number
  correct?: number
  total?: number
  delta?: number
  delta_ci95?: [number, number]
  matrix?: NightlyMatrix
  verdict?: string
  note?: string
  run_id?: string
  dataset_id?: string
  judge_failed_count?: number
  gate_reasons?: string[]
  regressions?: Record<string, string>
  regression_items?: QuestionItem[]
  fixed_items?: QuestionItem[]
}

const DEFAULT_NIGHTLY_DATASET = 'open-ragbench-subset-v2'

const props = defineProps<{ day: NightlyDayLite; detail?: { nightly?: NightlyDayLite; report_md?: string } }>()

defineEmits<{ (e: 'open-run', payload: { datasetId: string; runId: string }): void }>()

/** 归因机读码 → 大白话（机读码来自 compare_runs.attribute()，原始串留 tooltip） */
const BUCKET_PLAIN: Record<string, string> = {
  infra_anomaly: '评判基础设施抖动，非真回归',
  retrieval_regression: '检索变差：原来找得到的内容找不到了',
  refusal: '该答的题没给出答案',
  route_change: '作答处理路径变化',
  no_semantic_eval: '缺少语义评分',
  partial_coverage: '方向对但答得不全',
  wrong_conclusion: '内容相关但结论错了',
  severe_miss: '完全答偏',
}
const bucketPlain = (bucket?: string) => (bucket && BUCKET_PLAIN[bucket]) || bucket || '未知原因'
const bucketColor = (bucket?: string) => (bucket === 'infra_anomaly' ? 'default' : 'orange')

/** 列表页已回传整份 nightly.json，明细接口回来后用更全的那份 */
const cur = computed<NightlyDayLite>(() => props.detail?.nightly || props.day)

const pct = (value?: number) => (value == null ? '—' : `${(value * 100).toFixed(2)}%`)

const hasMatrix = computed(() => cur.value.matrix != null)
const matrixPf = computed(() => cur.value.matrix?.pf)

const chips = computed(() => {
  const m = cur.value.matrix || {}
  return [
    { label: '两晚都答对', value: m.pp, color: '#bfbfbf' },
    { label: '今晚修复', value: m.pf, color: '#52c41a' },
    { label: '今晚回退', value: m.fp, color: '#ff4d4f' },
    { label: '两晚都答错', value: m.ff, color: '#8c8c8c' },
  ]
})

/** 分行结论：一行一件事，不写门禁等内部术语；基线参照分写进差值句，不再单独展示 */
const analysisLines = computed<string[]>(() => {
  const day = cur.value
  if (day.state === 'error') return [day.note || '评测中断，未产出结果。']
  const dir = (day.delta ?? 0) >= 0 ? '高' : '低'
  const baseRef = day.overall_score != null && day.delta != null ? `（${pct(day.overall_score - day.delta)}）` : ''
  const lines = [`今晚答对 ${pct(day.overall_score)}，比基线${baseRef}${dir} ${(Math.abs(day.delta ?? 0) * 100).toFixed(2)} 个百分点。`]
  const m = day.matrix || {}
  if (m.pf != null || m.fp != null) {
    lines.push(`答对变答错 ${m.fp ?? '—'} 题，答错变答对 ${m.pf ?? '—'} 题。`)
  }
  lines.push(day.state === 'red'
    ? '整体明显变差，需要排查下方回退题目。'
    : '整体没有变差，正常波动。')
  if (day.judge_failed_count) {
    lines.push(`评判环节抖动 ${day.judge_failed_count} 题，已自动补判。`)
  }
  return lines
})

const regressions = computed<QuestionItem[]>(() => {
  const day = cur.value
  if (day.regression_items?.length) return day.regression_items
  return Object.entries(day.regressions || {}).map(([qid, bucket]) => ({ qid, bucket_detail: bucket }))
})
const fixed = computed<QuestionItem[]>(() => cur.value.fixed_items || [])
const fixedHeader = computed(() => {
  const total = matrixPf.value ?? fixed.value.length
  return fixed.value.length < total
    ? `新修复题目（昨晚答错 → 今晚答对，共 ${total} 题，展示 ${fixed.value.length} 题）`
    : `新修复题目（昨晚答错 → 今晚答对，${total} 题）`
})

// ── 过渡矩阵 donut（echarts，沿用 ApiKeyChart 的全量 import 惯例）──
const donutEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | undefined

function renderChart(): void {
  if (!donutEl.value || !hasMatrix.value) return
  if (!chart) chart = echarts.init(donutEl.value)
  const m = cur.value.matrix || {}
  const total = (m.pp || 0) + (m.pf || 0) + (m.fp || 0) + (m.ff || 0)
  chart.setOption({
    color: ['#bfbfbf', '#52c41a', '#ff4d4f', '#8c8c8c'],
    tooltip: { trigger: 'item', formatter: '{b}: {c} 题（{d}%）' },
    graphic: {
      type: 'text', left: 'center', top: 'middle',
      style: { text: `${total}`, fontSize: 20, fontWeight: 600, fill: '#888' },
    },
    series: [{
      type: 'pie', radius: ['62%', '82%'], avoidLabelOverlap: true,
      label: { show: false }, emphasis: { scale: false },
      data: [
        { name: '两晚都答对', value: m.pp ?? 0 },
        { name: '今晚修复', value: m.pf ?? 0 },
        { name: '今晚回退', value: m.fp ?? 0 },
        { name: '两晚都答错', value: m.ff ?? 0 },
      ],
    }],
  })
}

const handleResize = () => chart?.resize()

onMounted(async () => {
  await nextTick()
  renderChart()
  window.addEventListener('resize', handleResize)
})
watch(cur, async () => {
  await nextTick()
  renderChart()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = undefined
})
</script>

<style scoped>
.ndd {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
/* 总览：图 + 分行结论，横向铺满且可换行，不出横向滚动 */
.ndd-overview {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  flex-wrap: wrap;
  min-width: 0;
}
.ndd-overview__left {
  flex: 0 1 360px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ndd-analysis {
  flex: 1 1 320px;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ndd-chips {
  display: flex;
  gap: 8px 16px;
  flex-wrap: wrap;
}
.ndd-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary, rgba(0, 0, 0, 0.65));
  white-space: nowrap;
}
.ndd-chip b {
  color: var(--text-primary, rgba(0, 0, 0, 0.85));
  font-size: 15px;
}
.ndd-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.ndd-donut {
  width: 100%;
  max-width: 320px;
  height: 200px;
}
.ndd-analysis__line {
  margin: 0;
  font-size: 13px;
  line-height: 22px;
  color: var(--text-primary, rgba(0, 0, 0, 0.85));
}
.ndd-open-run {
  align-self: flex-start;
  padding-left: 0;
}
.ndd-alert {
  margin-top: 2px;
}
.ndd-collapses {
  background: transparent;
}
.ndd-report__raw {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 18px;
  max-height: 360px;
  overflow: auto;
}
.ndd-qlist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
  overflow: auto;
}
.ndd-qitem {
  border: 1px solid var(--border-color, rgba(5, 5, 5, 0.06));
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--card-bg, var(--bg-primary, #fff));
}
.ndd-qitem__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ndd-qitem__mark {
  font-size: 12px;
  color: var(--text-secondary, rgba(0, 0, 0, 0.45));
  white-space: nowrap;
}
.ndd-qitem__q {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 20px;
  color: var(--text-primary, rgba(0, 0, 0, 0.85));
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ndd-qitem--fixed .ndd-qitem__q {
  color: var(--text-secondary, rgba(0, 0, 0, 0.65));
}
</style>
