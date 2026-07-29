---
name: inventory-optimizer
description: 库存优化 - 安全库存计算和补货建议
scope: procurement
version: 1.0.0
---

# 库存优化技能

## 概述
基于历史消耗数据和供应商交货周期，计算最优安全库存和补货点。

## 核心功能
1. **安全库存计算**: 基于需求波动和补货周期
2. **补货点预警**: 当库存低于再订购点时触发建议
3. **ABC分类**: 按价值/消耗量对零部件分类管理
4. **呆滞料识别**: 识别长期未消耗的库存项

## 使用方式
调用 inventory_warning 获取预警数据，结合 order_statistics 分析消耗趋势。
