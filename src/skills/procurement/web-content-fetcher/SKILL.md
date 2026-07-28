---
name: web-content-fetcher
description: HTML转Markdown技能 - 将网页内容转换为结构化Markdown文本
scope: procurement
version: 1.0.0
---

# HTML转Markdown技能

## 概述
将抓取的HTML网页内容转换为结构化的Markdown格式，便于Agent理解和引用。

## 使用方式
```bash
python /skills/procurement/web-content-fetcher/fetcher.py --url <target_url> --output /output/content.md
```

## 参数说明
| 参数 | 必填 | 说明 |
|------|------|------|
| `--url` | 是 | 目标网页URL |
| `--output` | 否 | 输出Markdown路径，默认 /output/content.md |
| `--max-length` | 否 | 最大输出字符数，默认 8000 |

## 输出格式
纯Markdown文本，保留：
- 标题层级 (h1-h6)
- 列表 (ul/ol)
- 表格
- 链接
- 加粗/斜体

去除：
- 导航栏、页脚
- 广告区块
- 脚本/样式
- 冗余空白

## 依赖
- requests
- beautifulsoup4
- markdownify

## 配合使用
1. 先用 `web_search` 找到目标URL
2. 用本技能转换为Markdown
3. Agent直接阅读Markdown内容进行分析
