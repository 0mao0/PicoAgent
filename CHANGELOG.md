# Changelog

## 0.2.0

- refactor: 移除内置 SmartTree 组件，改为依赖 @angineer/smartree（^0.1.1），与 monorepo 结构统一，SmartTree 维护单一代码来源
- 对消费方：安装 @angineer/docs-ui 时会自动安装 @angineer/smartree，对外组件 API 不变

## 0.1.9

- feat: PDF 高亮定位统一居中——引用跳转、PDF 内点击、右侧索引树三个入口的 bbox 定位行为一致（同步 monorepo 0.2.16）

## 0.1.8

- feat: 引用定位逻辑共享化（useKnowledgeCitation 统一引用定位链路）
- fix: PDF 索引树懒加载修复（PDFParsedWorkspace 结构数据未全量加载时的处理）
- 同步 monorepo 0.2.14 改动

## 0.1.7

- feat: 溯源切换 activeHighlightId 时 bbox 纵向居中（centerActiveHighlight，DredgeAI 溯源需求）

## 0.1.6

- feat: PDF_Viewer 原生全文搜索回退（调用方未传 searchText/textContent 时逐页用 pdf.js 文本内容搜索）
- feat: PDF_Viewer 新增 title prop（替代“原文”标签显示文档标题）
- feat: 知识树库根虚拟节点、引用定位归一化、检索结果公式渲染等 monorepo 近期改动

## 0.1.5

- fix: PDF 搜索命中按文本+行距解析目标高亮块，修复编辑版/解析版 markdown 行号错位导致的错页定位
- fix: 文档加载时用 pdf.js 预取全部页真实高度种入虚拟布局，跳页/bbox 定位不再依赖估算收敛
- fix: 目标页未渲染时先跳页、渲染后按真实几何再次精确定位（一次点击完成两步）
- fix: 修复虚拟占位高度被 flex 容器压缩导致整篇不可滚动、需多次点击才到位的问题
- fix: 引用跳转只高亮目标块，不再展开整个章节
- chore: 清理 PDF 查看器损坏字符与调试日志

## 0.1.4

- feat: 流式加载 Loading aborted 静默降级为全量加载，并缓存失败源避免重复尝试
- chore: 移除文档切换/卸载调试日志

## 0.1.3

- feat: PDF_Viewer 支持 pdfPageRange 子集渲染（绝对页码、越界吸附）
- feat: 新增 pdf-loaded 加载完成事件

## 0.1.2

- feat: PDF 高亮悬停显示原文（hover 高亮命中项时展示对应原文片段）

## 0.1.1

- 同步 AnGIneer monorepo 最新代码：
  - 新增 citationTarget 引用目标归一化工具与测试；
  - 新增 highlightGroup 章节组高亮工具与测试；
  - PDF 查看器 / 解析工作区 / 知识树 / 知识引用等改进。
