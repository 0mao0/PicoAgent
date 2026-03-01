import { ref, watch } from 'vue'
import type { ThemeConfig } from '../types'

const THEME_KEY = 'angineer-theme'

export function useTheme() {
  const theme = ref<ThemeConfig>({
    primaryColor: '#1890ff',
    mode: 'light',
    compact: false
  })

  const loadTheme = () => {
    try {
      const saved = localStorage.getItem(THEME_KEY)
      if (saved) {
        theme.value = JSON.parse(saved)
      }
    } catch {
      console.warn('Failed to load theme')
    }
  }

  const saveTheme = () => {
    try {
      localStorage.setItem(THEME_KEY, JSON.stringify(theme.value))
    } catch {
      console.warn('Failed to save theme')
    }
  }

  const setTheme = (newTheme: Partial<ThemeConfig>) => {
    theme.value = { ...theme.value, ...newTheme }
    saveTheme()
  }

  const toggleDarkMode = () => {
    theme.value.mode = theme.value.mode === 'light' ? 'dark' : 'light'
    saveTheme()
  }

  const isDark = () => theme.value.mode === 'dark'

  watch(theme, saveTheme, { deep: true })

  loadTheme()

  return {
    theme,
    setTheme,
    toggleDarkMode,
    isDark
  }
}
