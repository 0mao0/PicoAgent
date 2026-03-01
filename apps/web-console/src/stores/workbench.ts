import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface Tab {
  key: string
  type: 'document' | 'sop' | 'gis' | 'code'
  title: string
  props: Record<string, any>
}

export const useWorkbenchStore = defineStore('workbench', () => {
  const tabs = ref<Tab[]>([])
  const activeTab = ref<string>('')

  const currentTab = computed(() => tabs.value.find(t => t.key === activeTab.value))

  const openTab = (tab: Tab) => {
    const existing = tabs.value.find(t => t.key === tab.key)
    if (!existing) {
      tabs.value.push(tab)
    }
    activeTab.value = tab.key
  }

  const closeTab = (key: string) => {
    const index = tabs.value.findIndex(t => t.key === key)
    if (index > -1) {
      tabs.value.splice(index, 1)
      if (activeTab.value === key) {
        activeTab.value = tabs.value[Math.max(0, index - 1)]?.key || ''
      }
    }
  }

  const setActiveTab = (key: string) => {
    activeTab.value = key
  }

  return {
    tabs,
    activeTab,
    currentTab,
    openTab,
    closeTab,
    setActiveTab
  }
})
