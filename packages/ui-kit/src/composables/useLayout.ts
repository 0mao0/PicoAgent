import { ref, computed } from 'vue'
import type { LayoutConfig } from '../types'

const LAYOUT_KEY = 'angineer-layout'

export function useLayout() {
  const config = ref<LayoutConfig>({
    leftPanelWidth: 280,
    rightPanelWidth: 380,
    showLeftPanel: true,
    showRightPanel: true
  })

  const loadConfig = () => {
    try {
      const saved = localStorage.getItem(LAYOUT_KEY)
      if (saved) {
        config.value = { ...config.value, ...JSON.parse(saved) }
      }
    } catch {
      console.warn('Failed to load layout config')
    }
  }

  const saveConfig = () => {
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(config.value))
    } catch {
      console.warn('Failed to save layout config')
    }
  }

  const toggleLeftPanel = () => {
    config.value.showLeftPanel = !config.value.showLeftPanel
    saveConfig()
  }

  const toggleRightPanel = () => {
    config.value.showRightPanel = !config.value.showRightPanel
    saveConfig()
  }

  const setLeftPanelWidth = (width: number) => {
    config.value.leftPanelWidth = width
    saveConfig()
  }

  const setRightPanelWidth = (width: number) => {
    config.value.rightPanelWidth = width
    saveConfig()
  }

  const leftPanelVisible = computed(() => config.value.showLeftPanel)
  const rightPanelVisible = computed(() => config.value.showRightPanel)

  loadConfig()

  return {
    config,
    toggleLeftPanel,
    toggleRightPanel,
    setLeftPanelWidth,
    setRightPanelWidth,
    leftPanelVisible,
    rightPanelVisible
  }
}
