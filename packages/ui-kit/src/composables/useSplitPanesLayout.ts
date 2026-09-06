/**
 * SplitPanes 布局状态持久化 composable。
 *
 * 真相源：KnowledgeParseWorkspace 的知识树三栏持久化（比例 localStorage + 拖拽换算钳制、
 * 收起状态持久化）。各三栏视图（知识库 / 评测集等）经由此 composable 共享同一套行为，
 * 不再各自手写字段读写与钳制逻辑。
 */
import { ref, type Ref } from 'vue'

export interface SplitPanesLayoutOptions {
  /** 面板比例存储的 localStorage key */
  storageKey: string
  /** 无存储或存储校验失败时的默认比例 */
  defaultLeftRatio?: number
  defaultRightRatio?: number
  /** resize / 恢复时的比例钳制区间 [min, max] */
  leftRatioRange?: [number, number]
  rightRatioRange?: [number, number]
  /** 左右比例之和超过该值视为无效（resize 不生效、存储不采纳），防止中间栏被挤没 */
  maxRatioSum?: number
  /** 收起状态持久化的 localStorage keys；不传则收起状态不落库 */
  collapsedStorageKeys?: { left: string; right: string }
  /** 容器宽度取值器：把 resize 回传的 px 宽度换算为比例 */
  getContainerWidth: () => number
}

export interface SplitPanesLayout {
  /** 绑定到 SplitPanes 的 :initial-left-ratio / :initial-right-ratio */
  panelRatios: Ref<{ left: number; right: number }>
  leftCollapsed: Ref<boolean>
  rightCollapsed: Ref<boolean>
  /** 绑定 @update:left-collapsed：更新状态并落库 */
  setLeftCollapsed: (value: boolean) => void
  /** 绑定 @update:right-collapsed：更新状态并落库 */
  setRightCollapsed: (value: boolean) => void
  /** 绑定 @resize：px→比例换算、钳制与落库（无效布局直接忽略） */
  onPanelResize: (leftSize: number, rightSize: number) => void
}

const clampRatio = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

export function useSplitPanesLayout(options: SplitPanesLayoutOptions): SplitPanesLayout {
  const {
    storageKey,
    defaultLeftRatio = 0.15,
    defaultRightRatio = 0.25,
    leftRatioRange = [0.1, 0.45],
    rightRatioRange = [0.16, 0.45],
    maxRatioSum = 0.85,
    collapsedStorageKeys,
    getContainerWidth,
  } = options

  const panelRatios = ref({ left: defaultLeftRatio, right: defaultRightRatio })

  const readCollapsed = (key: string) => localStorage.getItem(key) === 'true'
  const leftCollapsed = ref(collapsedStorageKeys ? readCollapsed(collapsedStorageKeys.left) : false)
  const rightCollapsed = ref(collapsedStorageKeys ? readCollapsed(collapsedStorageKeys.right) : false)

  const setLeftCollapsed = (value: boolean) => {
    leftCollapsed.value = value
    if (collapsedStorageKeys) localStorage.setItem(collapsedStorageKeys.left, String(value))
  }
  const setRightCollapsed = (value: boolean) => {
    rightCollapsed.value = value
    if (collapsedStorageKeys) localStorage.setItem(collapsedStorageKeys.right, String(value))
  }

  const onPanelResize = (leftSize: number, rightSize: number) => {
    const containerWidth = getContainerWidth()
    if (containerWidth <= 0) return
    const left = clampRatio(leftSize / containerWidth, leftRatioRange[0], leftRatioRange[1])
    const right = clampRatio(rightSize / containerWidth, rightRatioRange[0], rightRatioRange[1])
    if (left + right >= maxRatioSum) return
    panelRatios.value = { left, right }
    localStorage.setItem(storageKey, JSON.stringify(panelRatios.value))
  }

  // setup 期同步恢复历史比例（钳制 + 总和校验，损坏存储回退默认值）
  try {
    const saved = localStorage.getItem(storageKey)
    if (saved) {
      const parsed = JSON.parse(saved) as { left?: number; right?: number }
      const left = clampRatio(Number(parsed.left || defaultLeftRatio), leftRatioRange[0], leftRatioRange[1])
      const right = clampRatio(Number(parsed.right || defaultRightRatio), rightRatioRange[0], rightRatioRange[1])
      if (left + right < maxRatioSum) {
        panelRatios.value = { left, right }
      }
    }
  } catch {
    panelRatios.value = { left: defaultLeftRatio, right: defaultRightRatio }
  }

  return { panelRatios, leftCollapsed, rightCollapsed, setLeftCollapsed, setRightCollapsed, onPanelResize }
}
