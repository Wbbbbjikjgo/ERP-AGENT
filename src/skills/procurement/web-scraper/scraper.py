"""
网页抓取脚本 - 在沙箱内执行
用法: python scraper.py --url <target_url> [--output /output/scraped.json] [--selector body] [--timeout 30]
"""
import argparse
import json
import sys
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("安装依赖: requests, beautifulsoup4, lxml")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml", "-q"])
    import requests
    from bs4 import BeautifulSoup


def scrape_page(url: str, selector: str = "body", timeout: int = 30) -> dict:
    """抓取网页内容并提取结构化数据"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "lxml")

    # 提取标题
    title = soup.title.string.strip() if soup.title else ""

    # 提取指定选择器的文本
    target = soup.select_one(selector)
    content = target.get_text(separator="\n", strip=True) if target else ""

    # 提取表格
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)

    # 提取链接
    links = []
    for a in soup.find_all("a", href=True)[:50]:
        text = a.get_text(strip=True)
        if text:
            links.append({"text": text, "href": a["href"]})

    return {
        "url": url,
        "title": title,
        "content": content[:10000],  # 限制长度
        "tables": tables[:10],
        "links": links,
        "scraped_at": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="网页抓取工具")
    parser.add_argument("--url", required=True, help="目标URL")
    parser.add_argument("--output", default="/output/scraped.json", help="输出路径")
    parser.add_argument("--selector", default="body", help="CSS选择器")
    parser.add_argument("--timeout", type=int, default=30, help="超时秒数")
    args = parser.parse_args()

    try:
        result = scrape_page(args.url, args.selector, args.timeout)

        # 确保输出目录存在
        import os
        os.makedirs(os.path.dirname(args.output), exist_ok=True)

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"✓ 抓取成功: {result['title']}")
        print(f"  内容长度: {len(result['content'])} 字符")
        print(f"  表格数量: {len(result['tables'])}")
        print(f"  输出文件: {args.output}")

    except Exception as e:
        print(f"✗ 抓取失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
