---
name: web-scraper
description: 网页抓取技能 - 在沙箱内抓取指定URL的网页内容
scope: procurement
version: 1.0.0
---

# 网页抓取技能

## 概述
在沙箱环境中执行网页抓取，获取供应商报价页面、行业资讯等公开网页内容。

## 使用方式
```bash
python /skills/procurement/web-scraper/scraper.py --url <target_url> --output /output/scraped.json
```

## 参数说明
| 参数 | 必填 | 说明 |
|------|------|------|
| `--url` | 是 | 目标网页URL |
| `--output` | 否 | 输出JSON路径，默认 /output/scraped.json |
| `--selector` | 否 | CSS选择器，默认 body |
| `--timeout` | 否 | 超时秒数，默认 30 |

## 输出格式
```json
{
  "url": "https://...",
  "title": "页面标题",
  "content": "提取的文本内容",
  "tables": [["表头1", "表头2"], ["数据1", "数据2"]],
  "links": [{"text": "链接文字", "href": "https://..."}],
  "scraped_at": "2024-01-01T00:00:00"
}
```

## 依赖
- requests
- beautifulsoup4
- lxml

## 注意事项
- 仅在沙箱内执行，不影响宿主机
- 遵守 robots.txt 规则
- 单次请求超时30秒自动终止
- 仅抓取公开可访问页面
