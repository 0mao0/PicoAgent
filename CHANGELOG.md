# Changelog

## v0.1.1

- feat: npm registry 正式上架（@angineer/table-ui）

## v0.1.0

- 首次发布：通用表格组件 DataTable（自 AnGIneer ui-kit 拆分独立）
- 配置驱动筛选栏：input / select（多选）/ radio / switch，`v-model:query` 输出查询条件
- 列宽拖拽 + localStorage 持久化（storageKey）；容器宽度自适应填满（fillWidth / flex 弹性列）
- 卡片容器模式（内置 SectionCard，`card` 可关闭）
- 主题零配置：颜色经 `var(--table-*, var(--语义变量, 默认值))` 双回退，宿主可在 `:root` 覆盖 `--table-*` 单独定制
