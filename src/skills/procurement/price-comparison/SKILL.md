---
name: price-comparison
description: 价格对比 - 供应商报价比价分析
scope: procurement
version: 1.0.0
---

# 价格对比技能

## 概述
对比不同供应商对同一零部件的报价，分析价格差异原因，给出采购建议。

## 使用方式
1. 通过 web_fetch 获取供应商公开报价
2. 调用 part_search 获取 ERP 内采购价
3. 对比分析生成价格差异报告
4. 使用 generate_chart 生成对比图表

## 依赖
- web_fetch 工具
- generate_chart 工具
- part_search MCP 工具
