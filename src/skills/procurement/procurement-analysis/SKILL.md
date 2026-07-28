---
name: procurement-analysis
description: 采购分析5步流程 - 供应商/零部件/库存深度数据分析与可视化
scope: procurement
version: 1.0.0
---

# 采购分析操作手册

## 概述
本技能定义了采购分析专家的标准5步分析流程，用于对供应商、零部件、库存数据进行深度分析并生成可视化报告。

## 5步分析流程

### Step 1: 数据采集
- 调用 `supplier_query` / `supplier_page` 获取供应商数据
- 调用 `part_search` / `part_page` 获取零部件数据
- 调用 `inventory_warning` / `inventory_page` 获取库存数据
- 调用 `order_search_details` / `order_statistics` 获取订单数据

### Step 2: 数据清洗与整理
- 使用 pandas DataFrame 整理原始数据
- 处理缺失值、异常值
- 统一数据格式（日期、金额、数量）
- 计算衍生指标（均价、占比、增长率）

### Step 3: 多维度分析
根据用户需求选择分析维度：
- **价格分析**: 同类零部件不同供应商价格对比
- **质量分析**: 供应商信用评级分布、合格率
- **交付分析**: 交货准时率、平均交货周期
- **库存分析**: 安全库存达标率、周转率
- **趋势分析**: 月度采购金额/数量变化趋势

### Step 4: 可视化生成
- 调用 `generate_chart` 工具生成图表
- 参考 `/skills/procurement/chart_params.md` 选择合适图表类型
- 常用图表：
  - 供应商对比 → 分组柱状图 (bar_grouped)
  - 价格趋势 → 折线图 (line)
  - 占比分布 → 饼图 (pie)
  - 库存预警 → 水平条形图 (bar_horizontal)
  - 多维评估 → 雷达图 (radar)

### Step 5: 报告输出
- 汇总分析结论（Markdown格式）
- 包含关键数据表格
- 附带图表文件路径
- 给出采购建议

## 输出格式模板
```markdown
## 📊 [分析主题] 分析报告

### 数据概览
| 指标 | 数值 |
|------|------|
| ... | ... |

### 分析结论
1. ...
2. ...

### 图表
![图表标题](/path/to/chart.png)

### 采购建议
- ...
```

## 注意事项
- 数据量大时分页获取（每页50条）
- 图表中文显示需设置 matplotlib 字体
- 金额统一保留2位小数
- 分析结果需客观，避免主观臆断
