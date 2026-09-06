<template>
  <!-- 夜间维护单日明细：总览（矩阵图+分行结论）+ 三个折叠条（回退题/新修复题/评测报告） -->
  <div class="ndd">
    <div class="ndd-overview">
      <div class="ndd-overview__left">
        <div v-if="hasMatrix" ref="matrixChartEl" class="ndd-matrix-chart" />
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
            <a-tooltip :title="`${bucketPlain(item.bucket)}${item.bucket_detail ? `（${item.bucket_detail}）` : ''}`">
              <a-tag :color="bucketColor(item.bucket)" class="ndd-qitem__tag">{{ bucketShort(item.bucket) }}</a-tag>
            </a-tooltip>
            <a-tooltip :title="item.question || undefined">
              <p class="ndd-qitem__q">{{ item.question || `题目 ${item.qid.slice(0, 8)}` }}</p>
            </a-tooltip>
            <a-tooltip title="昨晚答对，今晚答错">
              <span class="ndd-qitem__mark ndd-qitem__mark--down">✓→✗</span>
            </a-tooltip>
          </li>
        </ul>
      </a-collapse-panel>

      <a-collapse-panel key="fixed" :header="fixedHeader">
        <ul class="ndd-qlist">
          <li v-for="item in fixed" :key="item.qid" class="ndd-qitem ndd-qitem--fixed">
            <a-tag color="success" class="ndd-qitem__tag">已修复</a-tag>
            <a-tooltip :title="item.question || undefined">
              <p class="ndd-qitem__q">{{ item.question || `题目 ${item.qid.slice(0, 8)}` }}</p>
            </a-tooltip>
            <a-tooltip title="昨晚答错，今晚答对">
              <span class="ndd-qitem__mark ndd-qitem__mark--up">✗→✓</span>
            </a-tooltip>
          </li>
        </ul>
      </a-collapse-panel>

      <a-collapse-panel v-if="detail?.report_md" key="report" header="评测报告（report.md）">
        <div class="ndd-md" v-html="reportHtml" />
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Empty } from 'ant-design-vue'
import * as echarts from 'echarts'
import { renderMarkdownToHtml } from '@angineer/aichat-ui/utils/markdown'

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
/** 条目行内的短标签（完整解释放 tooltip），保证一行放得下、不出横向滚动 */
const BUCKET_SHORT: Record<string, string> = {
  infra_anomaly: '评判抖动',
  retrieval_regression: '检索变差',
  refusal: '拒答',
  route_change: '路径变化',
  no_semantic_eval: '缺评',
  partial_coverage: '答得不全',
  wrong_conclusion: '结论错',
  severe_miss: '答偏',
}
const bucketPlain = (bucket?: string) => (bucket && BUCKET_PLAIN[bucket]) || bucket || '未知原因'
const bucketShort = (bucket?: string) => (bucket && BUCKET_SHORT[bucket]) || bucket || '未知'
const bucketColor = (bucket?: string) => (bucket === 'infra_anomaly' ? 'default' : 'orange')

/** 列表页已回传整份 nightly.json，明细接口回来后用更全的那份 */
const cur = computed<NightlyDayLite>(() => props.detail?.nightly || props.day)

const pct = (value?: number) => (value == null ? '—' : `${(value * 100).toFixed(2)}%`)

const hasMatrix = computed(() => cur.value.matrix != null)
const matrixPf = computed(() => cur.value.matrix?.pf)

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
/** report.md 走 aichat-ui 同款渲染器（表格/标题/列表；admin-web 本就经 AIChat/evals-ui 打入了该 chunk） */
const reportHtml = computed(() => renderMarkdownToHtml(props.detail?.report_md || '', ''))

const fixedHeader = computed(() => {
  const total = matrixPf.value ?? fixed.value.length
  return fixed.value.length < total
    ? `新修复题目（昨晚答错 → 今晚答对，共 ${total} 题，展示 ${fixed.value.length} 题）`
    : `新修复题目（昨晚答错 → 今晚答对，${total} 题）`
})

// ── 过渡矩阵横向柱状图（echarts，沿用 ApiKeyChart 的全量 import 惯例）──
const matrixChartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | undefined

function renderChart(): void {
  if (!matrixChartEl.value || !hasMatrix.value) return
  if (!chart) chart = echarts.init(matrixChartEl.value)
  const m = cur.value.matrix || {}
  const rows: Array<{ name: string; value: number; color: string }> = [
    { name: '两晚都答对', value: m.pp ?? 0, color: '#bfbfbf' },
    { name: '今晚修复', value: m.pf ?? 0, color: '#52c41a' },
    { name: '今晚回退', value: m.fp ?? 0, color: '#ff4d4f' },
    { name: '两晚都答错', value: m.ff ?? 0, color: '#8c8c8c' },
  ]
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}：{c} 题' },
    grid: { left: 4, right: 44, top: 4, bottom: 4, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: rows.map(r => r.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#999', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      barWidth: 14,
      data: rows.map(r => ({ value: r.value, itemStyle: { color: r.color, borderRadius: [0, 7, 7, 0] } })),
      label: { show: true, position: 'right', color: '#999', fontSize: 12 },
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
.ndd-matrix-chart {
  width: 100%;
  max-width: 360px;
  height: 140px;
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
/* 渲染后的 report.md：表格/标题/列表样式（v-html 内容需 :deep） */
.ndd-md {
  font-size: 13px;
  line-height: 22px;
  color: var(--text-primary, rgba(0, 0, 0, 0.85));
  max-height: 480px;
  overflow: auto;
  overflow-wrap: anywhere;
}
.ndd-md :deep(h1) { font-size: 17px; margin: 12px 0 8px; }
.ndd-md :deep(h2) { font-size: 15px; margin: 12px 0 6px; }
.ndd-md :deep(h3) { font-size: 14px; margin: 10px 0 6px; }
.ndd-md :deep(p) { margin: 4px 0; }
.ndd-md :deep(ul), .ndd-md :deep(ol) { margin: 4px 0; padding-left: 22px; }
.ndd-md :deep(li) { margin: 2px 0; }
.ndd-md :deep(strong) { font-weight: 600; }
.ndd-md :deep(code) {
  background: rgba(128, 128, 128, 0.12);
  border-radius: 3px;
  padding: 1px 5px;
  font-size: 12px;
}
.ndd-md :deep(pre code) { background: transparent; padding: 0; }
.ndd-md :deep(pre) {
  background: rgba(128, 128, 128, 0.08);
  border-radius: 6px;
  padding: 8px 10px;
  overflow: auto;
}
.ndd-md :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
}
.ndd-md :deep(th), .ndd-md :deep(td) {
  border: 1px solid var(--border-color, rgba(5, 5, 5, 0.08));
  padding: 4px 10px;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}
.ndd-md :deep(th) {
  background: var(--bg-secondary, rgba(128, 128, 128, 0.06));
  font-weight: 600;
}
.ndd-md :deep(tr:nth-child(even) td) {
  background: var(--bg-secondary, rgba(128, 128, 128, 0.03));
}
.ndd-qlist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 420px;
  overflow-y: auto;
  overflow-x: hidden;
}
/* 单行紧凑条目：标签 + 单行省略题干 + 状态符号，全部受父宽约束 */
.ndd-qitem {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  border: 1px solid var(--border-color, rgba(5, 5, 5, 0.06));
  border-radius: 6px;
  padding: 3px 8px;
  background: var(--card-bg, var(--bg-primary, #fff));
}
.ndd-qitem__tag {
  flex-shrink: 0;
  margin-inline-end: 0;
}
.ndd-qitem__q {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 12px;
  line-height: 18px;
  color: var(--text-primary, rgba(0, 0, 0, 0.85));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ndd-qitem__mark {
  flex-shrink: 0;
  font-size: 12px;
  white-space: nowrap;
}
.ndd-qitem__mark--down {
  color: #ff4d4f;
}
.ndd-qitem__mark--up {
  color: #52c41a;
}
.ndd-qitem--fixed .ndd-qitem__q {
  color: var(--text-secondary, rgba(0, 0, 0, 0.65));
}
</style>
