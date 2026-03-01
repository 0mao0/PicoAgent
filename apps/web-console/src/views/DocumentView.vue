<template>
  <div class="document-view">
    <div class="doc-header">
      <h2>{{ document?.title || '文档加载中...' }}</h2>
    </div>
    <div class="doc-content">
      <div v-if="loading" class="loading">
        <a-spin size="large" />
      </div>
      <div v-else-if="document" class="markdown-body" v-html="renderedContent" />
      <a-empty v-else description="文档不存在" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const loading = ref(true)
const document = ref<any>(null)

const renderedContent = computed(() => {
  return document.value?.content || ''
})

onMounted(async () => {
  const docId = route.params.id as string
  
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 500))
    
    document.value = {
      id: docId,
      title: '海港总体设计规范 - 第6章 进港航道、锚地',
      content: `
        <h1>6 进港航道、锚地及导助航设施</h1>
        <h2>6.1 一般规定</h2>
        <p>6.1.1 进港航道、锚地及导助航设施的设计应根据港口总体规划、到港船型、自然条件等因素综合确定。</p>
        <p>6.1.2 航道设计应满足船舶安全航行的要求，并应考虑航道维护和管理的需要。</p>
        <h2>6.2 航道建设规模及航行标准</h2>
        <p>6.2.1 航道建设规模应根据港口吞吐量预测、到港船型组合、船舶交通量等因素确定。</p>
        <h2>6.4 航道尺度</h2>
        <p>6.4.5 航道通航水深和设计水深应根据设计船型吃水、船舶航行下沉量、波浪产生的垂直运动、航道底质、水体密度、回淤强度和维护周期等因素确定。</p>
        <div class="formula">
          <p><strong>公式 6.4.5-1:</strong></p>
          <p>D₀ = T + Z₀ + Z₁ + Z₂ + Z₃</p>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>船舶吨级 DWT (10⁴t)</th>
              <th>4 kn</th>
              <th>6 kn</th>
              <th>8 kn</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>0</td><td>0.05</td><td>0.15</td><td>0.30</td></tr>
            <tr><td>2</td><td>0.08</td><td>0.25</td><td>0.45</td></tr>
            <tr><td>4</td><td>0.12</td><td>0.35</td><td>0.58</td></tr>
          </tbody>
        </table>
      `
    }
  } finally {
    loading.value = false
  }
})
</script>

<style lang="less" scoped>
.document-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.doc-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e8e8e8;
  
  h2 {
    margin: 0;
    font-size: 18px;
  }
}

.doc-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.loading {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.markdown-body {
  :deep(h1) {
    font-size: 24px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e8e8e8;
  }
  
  :deep(h2) {
    font-size: 20px;
    margin: 24px 0 12px;
  }
  
  :deep(p) {
    margin: 8px 0;
    line-height: 1.8;
  }
  
  :deep(.formula) {
    background: #f5f5f5;
    padding: 16px;
    border-radius: 4px;
    margin: 16px 0;
    font-family: 'Times New Roman', serif;
    font-size: 16px;
  }
  
  :deep(.data-table) {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    
    th, td {
      border: 1px solid #e8e8e8;
      padding: 8px 12px;
      text-align: center;
    }
    
    th {
      background: #fafafa;
    }
  }
}
</style>
