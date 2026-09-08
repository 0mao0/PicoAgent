<template>
  <div class="app-brand" :class="{ clickable: logoClickable }" @click="handleLogoClick">
    <img :src="logoHref" alt="AnGIneer logo" class="brand-logo" />
    <span class="brand-name">AnGIneer</span>

    <a-popover
      v-if="releaseNotes"
      trigger="hover"
      placement="bottomLeft"
      :overlay-style="{ maxWidth: '560px' }"
    >
      <template #title>v{{ appVersion }} 发版内容</template>
      <template #content>
        <div class="release-notes">
          <div v-for="(line, idx) in releaseNoteLines" :key="idx" class="release-notes__line">
            <span class="release-notes__dot" />{{ line }}
          </div>
        </div>
      </template>
      <span v-if="appVersion" class="brand-version">v{{ appVersion }}</span>
    </a-popover>
    <span v-else-if="appVersion" class="brand-version">v{{ appVersion }}</span>

    <a-tooltip>
      <template #title>{{ isDark ? '切换到浅色模式' : '切换到深色模式' }}</template>
      <a-button
        type="text"
        class="brand-theme-btn"
        :aria-label="isDark ? '切换到浅色模式' : '切换到深色模式'"
        @click="toggleTheme"
      >
        <template #icon>
          <BulbFilled v-if="isDark" />
          <BulbOutlined v-else />
        </template>
      </a-button>
    </a-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BulbFilled, BulbOutlined } from '@ant-design/icons-vue'
import { useTheme } from '../../composables/useTheme'

const props = withDefaults(defineProps<{ logoClickable?: boolean }>(), { logoClickable: false })
const emit = defineEmits<{ 'logo-click': [] }>()

const { isDark, toggleTheme } = useTheme()

/** 品牌区（logo + 名称 + 版本 hover 弹层 + 主题灯泡），userweb 与 adminweb 共用同一实现。
 * logo 用 BASE_URL 拼路径：admin 部署在 /admin/ 子路径下，写死 /favicon.svg 会 404。 */
const logoHref = import.meta.env.BASE_URL + 'favicon.svg'
const appVersion = import.meta.env.VITE_APP_VERSION || ''
const releaseNotes = import.meta.env.VITE_APP_RELEASE_NOTES || ''
/** 摘要按全/半角分号拆条，逐条换行展示 */
const releaseNoteLines = computed(() =>
  releaseNotes.split(/[；;]/).map((line) => line.trim()).filter(Boolean)
)

const handleLogoClick = () => {
  if (props.logoClickable) emit('logo-click')
}
</script>

<style lang="less" scoped>
.app-brand {
  display: flex;
  align-items: center;
  gap: 8px;

  &.clickable {
    cursor: pointer;
  }

  .brand-logo {
    width: 22px;
    height: 22px;
    display: block;
  }

  .brand-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .brand-version {
    font-size: 12px;
    color: var(--text-tertiary);
    cursor: default;
  }

  .brand-theme-btn {
    color: var(--text-secondary);
  }
}

.release-notes {
  max-height: 280px;
  overflow-y: auto;

  .release-notes__line {
    display: flex;
    gap: 6px;
    font-size: 12px;
    line-height: 1.7;
    color: var(--text-secondary);
    word-break: break-word;

    & + .release-notes__line {
      margin-top: 6px;
    }
  }

  .release-notes__dot {
    flex-shrink: 0;
    width: 4px;
    height: 4px;
    margin-top: 8px;
    border-radius: 50%;
    background: var(--primary-color, #1890ff);
  }
}
</style>
