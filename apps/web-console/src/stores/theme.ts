import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)

  const toggleTheme = () => {
    isDark.value = !isDark.value
  }

  const setTheme = (dark: boolean) => {
    isDark.value = dark
  }

  watch(isDark, (newVal) => {
    if (newVal) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    localStorage.setItem('angineer-theme', newVal ? 'dark' : 'light')
  }, { immediate: true })

  const initTheme = () => {
    const savedTheme = localStorage.getItem('angineer-theme')
    if (savedTheme) {
      isDark.value = savedTheme === 'dark'
    } else {
      isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
    }
  }

  return {
    isDark,
    toggleTheme,
    setTheme,
    initTheme
  }
})
