<template>
  <!-- 夜间维护单日明细：左=统计图表与结论分析，右=关键题目（面向非技术读者的措辞） -->
  <div class="ndd">
    <div class="ndd__left">
      <div class="ndd-chips">
        <span v-for="chip in chips" :key="chip.label" class="ndd-chip">
          <i class="ndd-dot" :style="{ background: chip.color }" />{{ chip.label }}
          <b>{{ chip.value ?? '—' }}</b>
        </span>
      </div>
      <div v-if="hasMatrix" ref="donutEl" class="ndd-donut" />
      <div class="ndd-analysis">
        <p class="ndd-analysis__main">{{ analysisMain }}</p>
        <a-alert
          v-for="(reason, i) in cur.gate_reasons || []"
          :key="i"
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
      <a-collapse v-if="detail?.report_md" class="ndd-report">
        <a-collapse-panel key="report" header="评测报告（report.md）">
          <pre class="ndd-report__raw">{{ detail?.report_md }}</pre>
        </a-collapse-panel>
      </a-collapse>
    </div>

    <div class="ndd__right">
      <div class="ndd-block-title">
        回退题目（昨晚答对 → 今晚答错）
        <span v-if="regressions.length" class="ndd-count">{{ regressions.length }} 题</span>
      </div>
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

      <template v-if="fixed.length">
        <div class="ndd-block-title">
          新修复题目（昨晚答错 → 今晚答对）
          <span v-if="matrixPf != null && matrixPf > fixed.length" class="ndd-count">
            共 {{ matrixPf }} 题，展示 {{ fixed.length }} 题
          </span>
        </div>
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
      </template>
    </div>
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
  gate_reasons?: string[]
  regressions?: Record<string, string>
  regression_items?: QuestionItem[]
  fixed_items?: QuestionItem[]
}

const props = defineProps<{ day: NightlyDayLite; detail?: { nightly?: NightlyDayLite; report_md?: string } }>()

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
const signedPp = (delta?: number) => (delta == null ? '—' : `${delta > 0 ? '+' : ''}${(delta * 100).toFixed(2)}`)

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

const analysisMain = computed(() => {
  const day = cur.value
  if (day.state === 'error') return day.note || '评测中断，未产出结果。'
  const ci = day.delta_ci95
  const ciText = ci ? `（95% 置信区间 ${signedPp(ci[0])} ~ ${signedPp(ci[1])}pp）` : ''
  const base = `今晚正确率 ${pct(day.overall_score)}，相对基线 ${signedPp(day.delta)} 个百分点${ciText}。`
  const m = day.matrix || {}
  const flow = `与基线相比：新修复 ${m.pf ?? '—'} 题、新回退 ${m.fp ?? '—'} 题。`
  return day.state === 'red'
    ? `${base}${flow}已触发回归门禁，需要排查。`
    : `${base}${flow}未触发回归门禁。`
})

const regressions = computed<QuestionItem[]>(() => {
  const day = cur.value
  if (day.regression_items?.length) return day.regression_items
  return Object.entries(day.regressions || {}).map(([qid, bucket]) => ({ qid, bucket_detail: bucket }))
})
const fixed = computed<QuestionItem[]>(() => cur.value.fixed_items || [])

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
  gap: 24px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.ndd__left {
  flex: 1.15 1 420px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ndd__right {
  flex: 1 1 320px;
  min-width: 0;
}
.ndd-chips {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.ndd-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary, rgba(0, 0, 0, 0.65));
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
  height: 200px;
}
.ndd-analysis__main {
  margin: 0;
  font-size: 13px;
  line-height: 22px;
  color: var(--text-primary, rgba(0, 0, 0, 0.85));
}
.ndd-alert {
  margin-top: 8px;
}
.ndd-report__raw {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 18px;
  max-height: 360px;
  overflow: auto;
}
.ndd-block-title {
  font-weight: 600;
  margin: 12px 0 8px;
}
.ndd-block-title:first-child {
  margin-top: 0;
}
.ndd-count {
  font-weight: 400;
  font-size: 12px;
  color: var(--text-secondary, rgba(0, 0, 0, 0.45));
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
