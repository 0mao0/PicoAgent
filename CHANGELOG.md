# Changelog

## 0.1.5

- fix: 修复主题 token 文件自引用失效（`--chat-x: var(--chat-x, …)` 为 CSS 循环引用，按规范整体无效）；组件使用处全部补齐 fallback，不导入 `./style` 也能正常渲染，`./style` 降级为可选的集中覆盖层
- fix: `--bg-secondary` 使用处补 fallback
- chore: 新增 `typecheck`（vue-tsc）与 `test` 脚本；README 收编主仓库（安装/导出/主题契约/token 表）

## 0.1.4

- feat: 同步 monorepo 0.2.16 改动——流式引用 tag 实时渲染（正文 [Kx]/[Tx] 标记在流式期间即可显示引用框）与引用 id 归一化（剥掉 target:/table:/formula:/figure:/chunk: 前缀）

## 0.1.3

- feat: AI 对话知识库切换响应式（切库后聊天作用域实时生效，修复挂载时快照问题）

## 0.1.2

- feat: 检索结果项支持 KaTeX 公式渲染（新增 searchSnippet 工具与测试）

## 0.1.1

- 同步 AnGIneer monorepo 最新代码：
  - 引用完整映射：citations 与 items 合并、按 marker 去重；
  - 证据数字圆圈与思考过程展示优化；
  - thinking 工具与测试补充。
