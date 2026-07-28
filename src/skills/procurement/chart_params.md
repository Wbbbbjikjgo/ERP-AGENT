# 图表参数速查表

## generate_chart 工具参数

```
generate_chart(
  chart_type: str,    # 图表类型（见下表）
  data: list[dict],   # 数据列表
  title: str,         # 图表标题
  x_field: str,       # X轴字段名
  y_field: str,       # Y轴字段名
  series_field: str,  # 系列字段（分组/多线时用）
  filename: str       # 输出文件名（不含路径）
)
```

## 26种图表类型

| 类型标识 | 中文名 | 适用场景 |
|---------|--------|---------|
| `bar` | 柱状图 | 单维度对比 |
| `bar_grouped` | 分组柱状图 | 多维度对比 |
| `bar_stacked` | 堆叠柱状图 | 组成分析 |
| `bar_horizontal` | 水平条形图 | 排名展示 |
| `line` | 折线图 | 趋势变化 |
| `line_multi` | 多折线图 | 多指标趋势 |
| `area` | 面积图 | 累积趋势 |
| `area_stacked` | 堆叠面积图 | 组成趋势 |
| `pie` | 饼图 | 占比分布 |
| `donut` | 环形图 | 占比（更美观） |
| `scatter` | 散点图 | 相关性分析 |
| `bubble` | 气泡图 | 三维相关 |
| `radar` | 雷达图 | 多维评估 |
| `heatmap` | 热力图 | 矩阵数据 |
| `box` | 箱线图 | 分布分析 |
| `violin` | 小提琴图 | 分布对比 |
| `histogram` | 直方图 | 频率分布 |
| `waterfall` | 瀑布图 | 增减分析 |
| `funnel` | 漏斗图 | 转化分析 |
| `gauge` | 仪表盘 | 达标率 |
| `treemap` | 矩形树图 | 层级占比 |
| `sunburst` | 旭日图 | 层级结构 |
| `sankey` | 桑基图 | 流向分析 |
| `candlestick` | K线图 | 价格波动 |
| `polar` | 极坐标图 | 周期数据 |
| `wordcloud` | 词云图 | 文本频率 |

## 常用场景映射

| 采购分析场景 | 推荐图表 | 参数示例 |
|------------|---------|---------|
| 供应商价格对比 | bar_grouped | x_field="supplier", y_field="price", series_field="part" |
| 月度采购趋势 | line | x_field="month", y_field="amount" |
| 库存预警 | bar_horizontal | x_field="part_name", y_field="stock" |
| 供应商信用分布 | pie | x_field="rating", y_field="count" |
| 零部件类别占比 | donut | x_field="category", y_field="count" |
| 供应商综合评估 | radar | x_field="dimension", y_field="score", series_field="supplier" |
| 采购金额组成 | treemap | x_field="category", y_field="amount" |

## 数据格式示例

```json
[
  {"supplier": "华胜机械", "price": 25.5, "part": "火花塞"},
  {"supplier": "恒达配件", "price": 28.0, "part": "火花塞"},
  {"supplier": "华胜机械", "price": 150.0, "part": "刹车片"}
]
```

## 注意事项
- 数据中的字段名必须与 x_field/y_field/series_field 一致
- 中文标题和标签已自动配置字体
- 输出路径固定为沙箱内 `/output/{filename}.png`
- 建议使用 download_sandbox_file 工具将图表下载到本地
