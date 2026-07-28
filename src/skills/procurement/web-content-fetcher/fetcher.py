"""
HTML转Markdown脚本 - 在沙箱内执行
用法: python fetcher.py --url <target_url> [--output /output/content.md] [--max-length 8000]
"""
import argparse
import sys
import os

try:
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
except ImportError:
    import subprocess
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "requests", "beautifulsoup4", "markdownify", "-q"
    ])
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md


def fetch_as_markdown(url: str, max_length: int = 8000) -> str:
    """获取网页并转换为Markdown"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "lxml")

    # 移除无用元素
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    # 移除广告类class
    for tag in soup.find_all(class_=lambda c: c and any(
        kw in str(c).lower() for kw in ["ad", "banner", "sponsor", "popup"]
    )):
        tag.decompose()

    # 获取主体内容
    main = soup.find("main") or soup.find("article") or soup.find("body")
    if not main:
        return ""

    # 转换为Markdown
    markdown = md(
        str(main),
        heading_style="ATX",
        bullets="-",
        strip=["img"],
    )

    # 清理多余空行
    lines = [line.rstrip() for line in markdown.split("\n")]
    cleaned = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned.append("")
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False

    result = "\n".join(cleaned).strip()

    # 限制长度
    if len(result) > max_length:
        result = result[:max_length] + "\n\n... (内容已截断)"

    return result


def main():
    parser = argparse.ArgumentParser(description="HTML转Markdown工具")
    parser.add_argument("--url", required=True, help="目标URL")
    parser.add_argument("--output", default="/output/content.md", help="输出路径")
    parser.add_argument("--max-length", type=int, default=8000, help="最大字符数")
    args = parser.parse_args()

    try:
        content = fetch_as_markdown(args.url, args.max_length)

        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✓ 转换成功")
        print(f"  内容长度: {len(content)} 字符")
        print(f"  输出文件: {args.output}")

    except Exception as e:
        print(f"✗ 转换失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
