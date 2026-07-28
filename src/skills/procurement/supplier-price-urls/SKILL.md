---
name: supplier-price-urls
description: 供应商报价URL映射 - 各供应商在线报价系统地址
scope: procurement
version: 1.0.0
---

# 供应商报价URL映射

## 概述
记录各主要供应商的在线报价系统URL，用于价格比对和市场竞争分析。

## URL映射表

| 供应商 | 报价系统URL | 备注 |
|--------|------------|------|
| 华胜机械制造 | https://example.com/huasheng/quote | 摩托车发动机配件 |
| 恒达配件 | https://example.com/hengda/price | 制动系统配件 |
| 金轮零部件 | https://example.com/jinlun/catalog | 传动系统配件 |
| 远航橡塑 | https://example.com/yuanhang/quote | 密封件/橡胶件 |
| 中信摩配 | https://example.com/zhongxin/price | 电气系统配件 |

## 使用场景
1. 当用户要求对比某零部件的市场价格时
2. 需要验证供应商报价是否合理时
3. 进行供应商竞争力分析时

## 使用方式
- 配合 `web_search` 工具搜索最新报价
- 配合 `web-scraper` 技能抓取报价页面
- 将抓取结果与 ERP 中的采购价进行对比

## 注意事项
- URL可能随时间变化，需定期验证
- 部分报价系统需要登录，仅抓取公开页面
- 价格数据仅供参考，实际以合同价为准
