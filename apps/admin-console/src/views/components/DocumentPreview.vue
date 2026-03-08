<template>
  <div class="doc-preview" :class="{ 'dark-mode': isDark }">
    <div class="preview-content">
      <div class="split-preview">
        <div class="split-pane split-pane-left">
          <div class="pane-title pane-title-with-actions">
            <div class="pane-title-main">
              <span class="pane-title-prefix">B1</span>
              <span class="doc-name" :title="node.title">{{ node.title }}</span>
              <a-tag v-if="node.status === 'failed'" color="error" class="parse-state-tag">
                解析失败
              </a-tag>
              <a-tag v-else-if="node.status === 'processing'" color="processing" class="parse-state-tag">
                解析中 {{ progressPercent }}%
              </a-tag>
            </div>
            <div class="pane-actions-left">
              <a-button
                type="primary"
                :loading="node.status === 'processing'"
                @click="$emit('parse', node)"
                class="parse-btn action-btn"
              >
                {{ parseButtonText }}
              </a-button>
              <a-switch
                :checked="switchChecked"
                :checked-children="'共享'"
                :un-checked-children="'本地'"
                @change="onVisibleChange"
                class="visible-switch action-switch"
              />
            </div>
          </div>
          <div v-if="node.status === 'processing' || node.status === 'failed'" class="parse-progress-row">
            <a-progress
              :percent="progressPercent"
              :status="node.parseError ? 'exception' : 'active'"
              size="small"
              class="processing-progress"
            />
            <span class="progress-text">{{ stageText }}</span>
          </div>
          <div class="file-preview">
            <iframe
              v-if="isPdf"
              :src="pdfViewerUrl"
              class="pdf-viewer"
              frameborder="0"
            />
            <div v-else-if="isOffice" class="office-preview">
              <iframe
                :src="officePreviewUrl"
                class="office-viewer"
                frameborder="0"
              />
            </div>
            <img
              v-else-if="isImage"
              :src="fileUrl"
              class="image-viewer"
              alt="文档预览"
            />
            <pre v-else-if="isText" class="text-viewer">{{ textContent }}</pre>
            <a-empty v-else description="暂不支持该格式预览，请下载后查看">
              <template #extra>
                <a-button type="primary" @click="downloadFile">下载文件</a-button>
              </template>
            </a-empty>
          </div>
        </div>

        <div class="split-pane split-pane-right">
          <div class="pane-title pane-title-with-actions b2-pane-title">
            <a-tabs v-model:activeKey="activeTab" size="small" class="b2-tabs">
              <a-tab-pane key="preview" tab="解析结果" />
              <a-tab-pane key="markdown" tab="Markdown" />
            </a-tabs>
            <div class="pane-actions-right">
              <a-select
                v-if="hasParsedContent"
                :value="strategyValue"
                style="width: 160px"
                @change="onStrategyChange"
              >
                <a-select-option value="A_structured">A 结果</a-select-option>
                <a-select-option value="B_mineru_rag">B 结果</a-select-option>
                <a-select-option value="C_pageindex">C 结果</a-select-option>
              </a-select>
              <a-button
                type="primary"
                :loading="ingestStatus === 'processing'"
                :disabled="!canIngest"
                @click="triggerIngest"
                class="ingest-btn action-btn"
              >
                {{ ingestButtonText }}
              </a-button>
              <a-button
                v-if="showStatsAction"
                :icon="h(PieChartOutlined)"
                class="action-btn stats-btn"
                @click="statsModalVisible = true"
              />
            </div>
          </div>

          <div class="b2-content">
            <div v-if="activeTab === 'preview'" class="markdown-preview" v-html="renderedMarkdown" />
            <div v-else class="markdown-edit-wrap">
              <a-textarea
                v-model:value="editableContent"
                class="markdown-editor"
              />
              <div class="markdown-edit-actions">
                <a-button
                  type="primary"
                  :disabled="!isContentDirty"
                  class="action-btn"
                  @click="saveMarkdown"
                >
                  保存
                </a-button>
              </div>
            </div>
            <a-empty
              v-if="!hasParsedContent && activeTab === 'preview'"
              description="请先解析文档，解析完成后将显示结果"
              class="b2-empty"
            />
          </div>
        </div>
      </div>
    </div>

    <a-modal
      v-model:open="ingestModalVisible"
      :title="ingestStatus === 'processing' ? '格式化入库中' : '格式化入库结果'"
      :footer="null"
      :mask-closable="ingestStatus !== 'processing'"
      :closable="ingestStatus !== 'processing'"
    >
      <div class="ingest-modal-content">
        <a-progress
          :percent="ingestProgressPercent"
          :status="ingestProgressStatus"
          size="default"
        />
        <div class="ingest-stage">{{ ingestStageText }}</div>
        <div v-if="ingestStatus === 'completed'" class="ingest-result">
          总条目 {{ structuredTotal }}
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model:open="statsModalVisible"
      title="入库分类统计"
      :footer="null"
    >
      <div class="stats-modal-content">
        <div class="stats-total">总条目：{{ structuredTotal }}</div>
        <div v-for="item in strategyStats" :key="item.key" class="stats-row">
          <span>{{ item.label }}</span>
          <a-tag color="blue">{{ item.value }}</a-tag>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { PieChartOutlined } from '@ant-design/icons-vue'
import type { TreeNode } from '@angineer/docs-ui'
import type { SmartTreeNode } from '@angineer/docs-ui'
import { useTheme } from '@angineer/ui-kit'

/**
 * 文档预览组件
 * 显示文档详情、操作按钮和解析后的内容
 */
interface Props {
  node: TreeNode
  content: string
  structuredStats?: Record<string, any>
  ingestStatus?: 'idle' | 'processing' | 'completed' | 'failed'
  ingestProgress?: number
  ingestStage?: string
}

const props = withDefaults(defineProps<Props>(), {})
const { isDark } = useTheme()

const emit = defineEmits<{
  parse: [node: SmartTreeNode]
  'toggle-visible': [node: SmartTreeNode]
  'save-content': [content: string]
  'change-strategy': [strategy: 'A_structured' | 'B_mineru_rag' | 'C_pageindex']
  'rebuild-structured': []
}>()

/** 获取文件路径 */
const filePath = computed(() => props.node.filePath || props.node.file_path || '')
const progressPercent = computed(() => Number(props.node.parseProgress || 0))
const ingestStatus = computed(() => props.ingestStatus || 'idle')
const ingestProgressPercent = computed(() => Number(props.ingestProgress || 0))
const activeTab = ref<'preview' | 'markdown'>('preview')
const ingestModalVisible = ref(false)
const statsModalVisible = ref(false)
const stageText = computed(() => {
  if (props.node.parseError) return `解析失败：${props.node.parseError}`
  const stage = props.node.parseStage || 'processing'
  const stageMap: Record<string, string> = {
    queued: '任务排队中',
    initializing: '正在初始化',
    mineru_processing: 'MinerU 解析中',
    reading_markdown: '读取 Markdown',
    saving_markdown: '保存解析结果',
    completed: '解析完成',
    failed: '解析失败'
  }
  return stageMap[stage] || stage
})
const ingestProgressStatus = computed(() => {
  if (ingestStatus.value === 'failed') return 'exception'
  if (ingestStatus.value === 'completed') return 'success'
  return 'active'
})
const ingestStageText = computed(() => {
  if (ingestStatus.value === 'failed') {
    return props.ingestStage || '格式化入库失败'
  }
  if (ingestStatus.value === 'completed') {
    return props.ingestStage || '格式化入库完成'
  }
  return props.ingestStage || '正在格式化入库'
})
const strategyValue = computed(() => props.node.strategy || 'A_structured')
const structuredTotal = computed(() => Number(props.structuredStats?.total || 0))
const hasParsedContent = computed(() => Boolean((props.content || '').trim()))
const parseButtonText = computed(() => {
  if (props.node.status === 'completed') return '重新解析'
  if (props.node.status === 'failed') return '重新解析'
  if (props.node.status === 'processing') return '解析中...'
  return '开始解析'
})
const ingestButtonText = computed(() => (structuredTotal.value > 0 ? '重新入库' : '格式化入库'))
const strategyTypeCount = (type: string) => {
  const strategy = strategyValue.value
  return Number(props.structuredStats?.strategies?.[strategy]?.[type] || 0)
}
const strategyStats = computed(() => ([
  { key: 'heading', label: '标题', value: strategyTypeCount('heading') },
  { key: 'clause', label: '条款', value: strategyTypeCount('clause') },
  { key: 'table', label: '表格', value: strategyTypeCount('table') },
  { key: 'image', label: '图片', value: strategyTypeCount('image') }
]))
const showStatsAction = computed(() => structuredTotal.value > 0 && ingestStatus.value !== 'processing')

/** 获取文件扩展名 */
const fileExtension = computed(() => {
  const path = filePath.value
  if (!path) return ''
  const match = path.match(/\.([a-zA-Z0-9]+)$/)
  return match ? match[1].toLowerCase() : ''
})

/** 判断是否为 PDF */
const isPdf = computed(() => fileExtension.value === 'pdf')

/** 判断是否为 Office 文档 */
const isOffice = computed(() => {
  const officeExts = ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']
  return officeExts.includes(fileExtension.value)
})

/** 判断是否为图片 */
const isImage = computed(() => {
  const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']
  return imageExts.includes(fileExtension.value)
})

/** 判断是否为文本文件 */
const isText = computed(() => {
  const textExts = ['txt', 'md', 'json', 'xml', 'csv', 'log', 'js', 'ts', 'py', 'java', 'cpp', 'c', 'h', 'html', 'css']
  return textExts.includes(fileExtension.value)
})

/** 文件 URL */
const fileUrl = computed(() => {
  if (!filePath.value) return ''
  // 如果路径已经是完整 URL，直接返回
  if (filePath.value.startsWith('http')) return filePath.value
  return `/api/files?path=${encodeURIComponent(filePath.value)}`
})
const pdfViewerUrl = computed(() => {
  if (!fileUrl.value) return ''
  if (fileUrl.value.includes('#')) {
    return `${fileUrl.value}&view=FitH`
  }
  return `${fileUrl.value}#view=FitH`
})

/** Office 文档预览 URL（使用微软在线预览服务） */
const officePreviewUrl = computed(() => {
  if (!fileUrl.value) return ''
  return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(window.location.origin + fileUrl.value)}`
})

/** 文本文件内容 */
const textContent = ref('')
const editableContent = ref('')
const switchChecked = ref(Boolean(props.node.visible))
const canIngest = computed(() => !isContentDirty.value)
const isContentDirty = computed(() => editableContent.value !== (props.content || ''))

/** 加载文本文件内容 */
const loadTextContent = async () => {
  if (!isText.value || !fileUrl.value) return
  try {
    const response = await fetch(fileUrl.value)
    textContent.value = await response.text()
  } catch (error) {
    textContent.value = '加载文件内容失败'
  }
}

const saveMarkdown = () => {
  emit('save-content', editableContent.value)
}

const triggerIngest = () => {
  ingestModalVisible.value = true
  emit('rebuild-structured')
}

const onStrategyChange = (value: 'A_structured' | 'B_mineru_rag' | 'C_pageindex') => {
  emit('change-strategy', value)
}

const onVisibleChange = (checked: boolean) => {
  switchChecked.value = checked
  emit('toggle-visible', { ...props.node, visible: checked })
}

/** 下载文件 */
const downloadFile = () => {
  if (!fileUrl.value) return
  const link = document.createElement('a')
  link.href = fileUrl.value
  link.download = props.node.title
  link.click()
}

/** 监听文件路径变化，加载文本内容 */
watch(filePath, () => {
  if (isText.value) {
    loadTextContent()
  }
}, { immediate: true })

watch(() => props.content, (value) => {
  editableContent.value = value || ''
}, { immediate: true })

watch(() => props.node.key, () => {
  activeTab.value = 'preview'
  ingestModalVisible.value = false
  statsModalVisible.value = false
})

watch(() => props.node.visible, (value) => {
  switchChecked.value = Boolean(value)
}, { immediate: true })

watch(ingestStatus, (value) => {
  if (value === 'processing') {
    ingestModalVisible.value = true
  }
})

const renderMarkdown = (content: string): string => {
  if (!content) return ''
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/\n/g, '<br/>')
}

const renderedMarkdown = computed(() => renderMarkdown(editableContent.value || props.content || ''))
</script>

<style lang="less" scoped>
.doc-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;

  .preview-content {
    flex: 1;
    overflow: hidden;
    padding: 0;

    .split-preview {
      display: flex;
      height: 100%;
      min-height: 500px;

      .split-pane {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        min-height: 0;
      }

      .split-pane-left {
        border-right: 1px solid #f0f0f0;
      }

      .pane-title {
        font-size: 13px;
        color: #595959;
        padding: 10px 12px;
        border-bottom: 1px solid #f0f0f0;
        background: #fff;
      }

      .pane-title-with-actions {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        min-height: 48px;
      }

      .pane-title-main {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        flex: 1;
      }

      .pane-title-prefix {
        color: #8c8c8c;
        font-weight: 600;
      }

      .doc-name {
        font-size: 14px;
        font-weight: 600;
        color: #262626;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .parse-state-tag {
        margin-inline-start: 2px;
      }

      .pane-actions-left,
      .pane-actions-right {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }

      .pane-actions-right {
        justify-content: flex-end;
      }

      .b2-pane-title {
        border-bottom: 0;
      }

      .b2-tabs {
        flex: 1;
        min-width: 0;

        :deep(.ant-tabs-nav) {
          margin: 0;
        }

        :deep(.ant-tabs-tab) {
          padding: 6px 0;
          font-weight: 500;
        }
      }

      .parse-progress-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-bottom: 1px solid #f0f0f0;
        background: #fafafa;
      }

      .b2-content {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        position: relative;
      }

      .markdown-edit-wrap {
        display: flex;
        flex-direction: column;
        height: 100%;
      }

      .markdown-edit-actions {
        display: flex;
        justify-content: flex-end;
        padding: 8px 12px 12px;
        border-top: 1px solid #f0f0f0;
      }

      .b2-empty {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: transparent;
      }
    }

    .file-preview {
      height: 100%;

      .pdf-viewer {
        width: 100%;
        height: 100%;
        min-height: 500px;
      }

      .office-preview {
        width: 100%;
        height: 100%;
        min-height: 500px;

        .office-viewer {
          width: 100%;
          height: 100%;
          min-height: 500px;
        }
      }

      .image-viewer {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        display: block;
        margin: 0 auto;
      }

      .text-viewer {
        background: #f6f8fa;
        padding: 16px;
        border-radius: 6px;
        overflow: auto;
        max-height: 100%;
        font-size: 13px;
        line-height: 1.6;
        white-space: pre-wrap;
        word-wrap: break-word;
        margin: 16px;
      }
    }

    .markdown-preview {
      padding: 16px;
      overflow: auto;
      height: 100%;
      font-size: 14px;
      line-height: 1.75;
      color: #262626;

      :deep(table) {
        width: 100%;
        border-collapse: collapse;
      }

      :deep(td),
      :deep(th) {
        border: 1px solid #f0f0f0;
        padding: 6px 8px;
      }

      pre {
        background: #f6f8fa;
        padding: 16px;
        border-radius: 6px;
        overflow: auto;
        max-height: 400px;
        font-size: 13px;
        line-height: 1.6;
      }
    }

    .markdown-editor {
      margin: 12px;
      flex: 1;
      min-height: 0;

      :deep(.ant-input-textarea) {
        height: 100%;
      }

      :deep(.ant-input) {
        height: 100% !important;
        resize: none;
        font-size: 13px;
        line-height: 1.6;
      }
    }
  }

  .processing-progress {
    flex: 0 0 250px;
    margin: 0;
  }

  .progress-text {
    color: #8c8c8c;
    font-size: 12px;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 60px;
  }

  .action-btn {
    height: 32px;
    border-radius: 8px;
    font-weight: 500;
    padding: 0 14px;
  }

  .action-switch {
    min-width: 78px;
    height: 32px;
    line-height: 30px;
    border-radius: 16px;

    :deep(.ant-switch-handle) {
      top: 3px;
    }

    :deep(.ant-switch-inner) {
      font-size: 12px;
      white-space: nowrap;
    }
  }

  .stats-btn {
    width: 32px;
    min-width: 32px;
    padding: 0;
    display: inline-flex;
    justify-content: center;
  }

  .ingest-modal-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 6px;
  }

  .ingest-stage {
    font-size: 13px;
    color: #595959;
  }

  .ingest-result {
    font-size: 14px;
    color: #1677ff;
    font-weight: 600;
  }

  .stats-modal-content {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .stats-total {
    font-weight: 600;
    color: #262626;
  }

  .stats-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &.dark-mode {
    background: #141414;

    .preview-content {
      .split-preview {
        .split-pane-left,
        .pane-title {
          border-color: #303030;
        }
      }

      .file-preview {
        .text-viewer {
          background: #272727;
          color: rgba(255, 255, 255, 0.85);
        }
      }

      .markdown-preview {
        color: rgba(255, 255, 255, 0.85);

        pre {
          background: #272727;
          color: rgba(255, 255, 255, 0.85);
        }
      }
    }
  }
}
</style>
