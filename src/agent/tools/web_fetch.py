"""
Web 抓取 & Skill 下载工具
- web_fetch: 获取任意 URL 的文本内容（HTML→纯文本 / JSON / Markdown）
- install_skill: 从 URL 下载 Skill 文件并安装到本地 skills 目录。
"""
import os
import re
import httpx
from pathlib import Path
from langchain_core.tools import tool

from ..log_utils import agent_logger

# Skills 目录：项目根/src/skills
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "src" / "skills"


def _strip_html(html: str) -> str:
    """简易 HTML → 纯文本（去标签、合并空白）"""
    # 移除 script/style
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 移除所有标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 合并空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


@tool
def web_fetch(url: str, max_chars: int = 8000) -> str:
    """获取指定 URL 的网页内容（转为纯文本）。

    可用于：
    - 查看技术文档、API 说明
    - 获取 Skill 文件内容
    - 阅读在线资源

    Args:
        url: 完整的 HTTP/HTTPS 地址
        max_chars: 返回内容最大字符数（默认8000）

    Returns:
        网页文本内容或错误信息
    """
    if not url.startswith(("http://", "https://")):
        return "错误: URL 必须以 http:// 或 https:// 开头"

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=20,
            headers={"User-Agent": "ERP-Agent/1.0 (Skill Downloader)"},
        )

        if response.status_code != 200:
            return f"请求失败: HTTP {response.status_code}"

        content_type = response.headers.get("content-type", "")
        text = response.text

        # HTML → 纯文本
        if "text/html" in content_type:
            text = _strip_html(text)

        # 截断
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [内容已截断，共 {len(response.text)} 字符]"

        agent_logger.info(f"web_fetch: {url} ({len(text)} chars)")
        return text

    except httpx.TimeoutException:
        return f"请求超时: {url}"
    except Exception as e:
        agent_logger.error(f"web_fetch error: {e}")
        return f"获取失败: {str(e)}"


@tool
def install_skill(url: str, skill_name: str = "") -> str:
    """从 URL 下载并安装 Skill 到本地。

    Skill 文件为 Markdown 格式（.md），下载后存入 skills 目录即可被 Agent 使用。

    Args:
        url: Skill 文件的下载地址（.md 或纯文本）
        skill_name: 技能名称（不含扩展名）。为空则从 URL 自动提取。

    Returns:
        安装结果说明
    """
    if not url.startswith(("http://", "https://")):
        return "错误: URL 必须以 http:// 或 https:// 开头"

    # 自动提取 skill 名称
    if not skill_name:
        # 从 URL 路径提取文件名
        path_part = url.rstrip("/").split("/")[-1]
        skill_name = re.sub(r"\.(md|txt|markdown)$", "", path_part, flags=re.IGNORECASE)
        if not skill_name:
            skill_name = "downloaded_skill"

    # 确保名称安全
    skill_name = re.sub(r"[^\w\-]", "_", skill_name)

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=20,
            headers={"User-Agent": "ERP-Agent/1.0 (Skill Installer)"},
        )

        if response.status_code != 200:
            return f"下载失败: HTTP {response.status_code}"

        content = response.text
        if not content.strip():
            return "错误: 下载内容为空"

        # 确保 skills 目录存在
        skills_dir = Path(SKILLS_DIR)
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 写入文件
        file_path = skills_dir / f"{skill_name}.md"
        file_path.write_text(content, encoding="utf-8")

        agent_logger.info(f"Skill installed: {skill_name} from {url}")
        return (
            f"✅ Skill 安装成功!\n"
            f"名称: {skill_name}\n"
            f"路径: {file_path}\n"
            f"大小: {len(content)} 字符\n"
            f"来源: {url}\n\n"
            f"该 Skill 已可用，Agent 在后续对话中会自动加载。"
        )

    except httpx.TimeoutException:
        return f"下载超时: {url}"
    except Exception as e:
        agent_logger.error(f"install_skill error: {e}")
        return f"安装失败: {str(e)}"
