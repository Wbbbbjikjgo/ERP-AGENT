"""
文档生成工具（Harness — 结构化文档输出）
支持生成 Markdown、HTML、CSV、JSON、纯文本报告。

Agent 在分析完数据后，可以使用此工具将结果输出为可下载的文件，
而不仅仅是在聊天中显示文本。

使用场景：
- 采购分析报告 → Markdown
- 供应商对比表 → CSV / HTML Table
- 数据导出 → JSON
- 会议纪要 → Markdown / HTML
"""
import os
import json
import csv
import io
from pathlib import Path
from datetime import datetime
from langchain_core.tools import tool

from ..log_utils import agent_logger

DOWNLOAD_DIR = Path(__file__).parent.parent.parent / "download"


@tool
def generate_document(
    title: str,
    content: str,
    format: str = "markdown",
    filename: str = "",
) -> str:
    """生成结构化文档文件（Markdown/HTML/CSV/JSON/纯文本）。

    将分析结果、报告、数据表格等输出为可下载的文件。

    Args:
        title: 文档标题
        content: 文档内容。根据格式不同：
            - markdown: Markdown 格式文本
            - html: HTML 格式（自动包装完整页面）
            - csv: CSV 格式（每行一条记录，逗号分隔）
            - json: JSON 格式字符串
            - text: 纯文本
        format: 输出格式（markdown/html/csv/json/text），默认 markdown
        filename: 文件名（不含扩展名，默认自动生成）

    Returns:
        文件路径和下载链接
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    if not filename:
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:30])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}"

    format = format.lower().strip()

    try:
        if format == "markdown" or format == "md":
            return _generate_markdown(title, content, filename)
        elif format == "html":
            return _generate_html(title, content, filename)
        elif format == "csv":
            return _generate_csv(title, content, filename)
        elif format == "json":
            return _generate_json(title, content, filename)
        elif format == "text" or format == "txt":
            return _generate_text(title, content, filename)
        else:
            return f"不支持的格式: {format}。支持: markdown, html, csv, json, text"
    except Exception as e:
        agent_logger.error(f"Document generation error: {e}")
        return f"文档生成失败: {str(e)}"


def _generate_markdown(title: str, content: str, filename: str) -> str:
    """生成 Markdown 文档"""
    md_content = f"# {title}\n\n"
    md_content += f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
    md_content += "---\n\n"
    md_content += content

    file_path = DOWNLOAD_DIR / f"{filename}.md"
    file_path.write_text(md_content, encoding="utf-8")

    return _build_result(title, "Markdown", file_path)


def _generate_html(title: str, content: str, filename: str) -> str:
    """生成 HTML 文档（完整页面，含样式）"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            color: #333;
            line-height: 1.6;
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 2px solid #2563EB;
            padding-bottom: 10px;
        }}
        .meta {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border: 1px solid #ddd;
        }}
        th {{
            background-color: #f5f5f5;
            font-weight: 600;
        }}
        tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .section {{
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="meta">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    <div class="section">
        {content}
    </div>
</body>
</html>"""

    file_path = DOWNLOAD_DIR / f"{filename}.html"
    file_path.write_text(html, encoding="utf-8")

    return _build_result(title, "HTML", file_path)


def _generate_csv(title: str, content: str, filename: str) -> str:
    """生成 CSV 文件"""
    file_path = DOWNLOAD_DIR / f"{filename}.csv"

    # 尝试解析 content 为表格数据
    try:
        # 尝试 JSON 列表格式
        data = json.loads(content) if content.strip().startswith("[") else None
        if isinstance(data, list) and len(data) > 0:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        else:
            # 纯文本逐行写入
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(f"# {title}\n")
                for line in content.strip().split('\n'):
                    f.write(line + '\n')
    except (json.JSONDecodeError, AttributeError):
        with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(f"# {title}\n")
            for line in content.strip().split('\n'):
                f.write(line + '\n')

    return _build_result(title, "CSV", file_path)


def _generate_json(title: str, content: str, filename: str) -> str:
    """生成 JSON 文件"""
    file_path = DOWNLOAD_DIR / f"{filename}.json"

    # 尝试解析为 JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"title": title, "content": content, "generated_at": datetime.now().isoformat()}

    wrapper = {
        "title": title,
        "generated_at": datetime.now().isoformat(),
        "data": data,
    }

    file_path.write_text(
        json.dumps(wrapper, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return _build_result(title, "JSON", file_path)


def _generate_text(title: str, content: str, filename: str) -> str:
    """生成纯文本文件"""
    text = f"{'=' * 60}\n"
    text += f"  {title}\n"
    text += f"{'=' * 60}\n"
    text += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    text += f"{'=' * 60}\n\n"
    text += content

    file_path = DOWNLOAD_DIR / f"{filename}.txt"
    file_path.write_text(text, encoding="utf-8")

    return _build_result(title, "纯文本", file_path)


def _build_result(title: str, format_name: str, file_path: Path) -> str:
    """构建统一的返回结果"""
    file_size = file_path.stat().st_size
    download_url = f"http://localhost:8000/api/download/{file_path.name}"

    agent_logger.info(f"Document generated: {file_path.name} ({file_size} bytes)")
    return (
        f"✅ 文档生成成功!\n"
        f"标题: {title}\n"
        f"格式: {format_name}\n"
        f"文件大小: {file_size / 1024:.1f} KB\n"
        f"下载链接: {download_url}\n"
        f"本地路径: {file_path}"
    )


@tool
def generate_table_report(
    title: str,
    headers: str,
    rows: str,
    format: str = "markdown",
) -> str:
    """生成表格报告（支持 Markdown / HTML / CSV 格式）。

    专门用于将结构化数据（如供应商列表、零部件清单、订单明细）
    输出为格式化的表格文件。

    Args:
        title: 报告标题
        headers: 表头 JSON 数组字符串，如 ["供应商", "价格", "评分"]
        rows: 数据行 JSON 二维数组字符串，如 [["博世", 25.5, "A"], ["电装", 28.0, "B"]]
        format: 输出格式（markdown/html/csv），默认 markdown

    Returns:
        文件路径和下载链接
    """
    try:
        header_list = json.loads(headers) if isinstance(headers, str) else headers
        row_list = json.loads(rows) if isinstance(rows, str) else rows
    except json.JSONDecodeError as e:
        return f"数据格式错误: {e}。headers 和 rows 必须是有效的 JSON 数组。"

    if not isinstance(header_list, list) or not isinstance(row_list, list):
        return "错误: headers 必须是一维数组，rows 必须是二维数组"

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:30])
    base_name = f"{safe_title}_{timestamp}"

    format = format.lower().strip()

    if format in ("markdown", "md"):
        content = _build_md_table(header_list, row_list)
        return generate_document.invoke({
            "title": title, "content": content, "format": "markdown", "filename": base_name
        })
    elif format == "html":
        content = _build_html_table(header_list, row_list)
        return generate_document.invoke({
            "title": title, "content": content, "format": "html", "filename": base_name
        })
    elif format == "csv":
        data = [dict(zip(header_list, row)) for row in row_list]
        content = json.dumps(data, ensure_ascii=False)
        return generate_document.invoke({
            "title": title, "content": content, "format": "csv", "filename": base_name
        })
    else:
        return f"不支持的格式: {format}。支持: markdown, html, csv"


def _build_md_table(headers: list, rows: list) -> str:
    """构建 Markdown 表格"""
    lines = []
    # 表头
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    # 数据行
    for row in rows:
        cells = [str(c) for c in row]
        # 补齐列数
        while len(cells) < len(headers):
            cells.append("")
        lines.append("| " + " | ".join(cells[:len(headers)]) + " |")
    return "\n".join(lines)


def _build_html_table(headers: list, rows: list) -> str:
    """构建 HTML 表格"""
    lines = ["<table>"]
    lines.append("  <thead><tr>")
    for h in headers:
        lines.append(f"    <th>{h}</th>")
    lines.append("  </tr></thead>")
    lines.append("  <tbody>")
    for row in rows:
        lines.append("    <tr>")
        for c in row:
            lines.append(f"      <td>{c}</td>")
        lines.append("    </tr>")
    lines.append("  </tbody>")
    lines.append("</table>")
    return "\n".join(lines)
