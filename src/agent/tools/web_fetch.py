"""
Web 抓取 & Skill 下载工具
- web_fetch: 获取任意 URL 的文本内容（HTML→纯文本 / JSON / Markdown）
- install_skill: 从 URL 下载完整 Skill 文件夹（含 SKILL.md + 脚本 + 依赖）并安装。

Skill 标准结构：
  skill-name/
    SKILL.md          # 技能定义（必须有）
    scraper.py        # 脚本文件（可选）
    requirements.txt  # 依赖（可选）
    assets/           # 资源文件（可选）
"""
import os
import re
import io
import zipfile
import tarfile
import httpx
import shutil
from pathlib import Path
from langchain_core.tools import tool

from ..log_utils import agent_logger

# Skills 目录：项目根/src/skills
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "src" / "skills"


def _strip_html(html: str) -> str:
    """简易 HTML → 纯文本（去标签、合并空白）"""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
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


# ============================================================
# Skill 安装（完整文件夹）
# ============================================================

@tool
def install_skill(url: str, skill_name: str = "") -> str:
    """从 URL 下载并安装完整 Skill 到本地。

    支持四种来源：
    1. GitHub 仓库 ZIP（如 https://github.com/user/repo/archive/refs/heads/main.zip）
    2. 任意 ZIP/TAR.GZ 压缩包（包含 SKILL.md 的文件夹）
    3. 单个 SKILL.md 文件 URL
    4. GitHub 仓库页面（自动转换为 ZIP 下载）

    标准 Skill 文件夹结构：
      skill-name/
        SKILL.md          # 技能定义（必须）
        *.py              # 脚本（可选）
        requirements.txt  # 依赖（可选）

    Args:
        url: Skill 的下载地址（ZIP 压缩包、GitHub 仓库、或 .md 文件）
        skill_name: 技能名称。为空则从 URL 自动提取。

    Returns:
        安装结果说明（含安装路径和文件列表）
    """
    if not url.startswith(("http://", "https://")):
        return "错误: URL 必须以 http:// 或 https:// 开头"

    # 自动转换 GitHub 仓库页面为 ZIP 下载链接
    url = _normalize_github_url(url)

    # 自动提取 skill 名称
    if not skill_name:
        skill_name = _extract_skill_name(url)

    # 确保名称安全
    skill_name = re.sub(r"[^\w\-]", "_", skill_name)

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "ERP-Agent/1.0 (Skill Installer)"},
        )

        if response.status_code != 200:
            return f"下载失败: HTTP {response.status_code}"

        # 判断内容类型
        content_type = response.headers.get("content-type", "")
        content_length = len(response.content)

        if content_length == 0:
            return "错误: 下载内容为空"

        # 确保 skills 目录存在
        skills_dir = Path(SKILLS_DIR)
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 根据内容类型选择安装方式
        if _is_archive(url, content_type):
            # 压缩包：解压完整文件夹
            return _install_from_archive(
                response.content, url, content_type, skill_name, skills_dir
            )
        else:
            # 单文件（通常是 .md）：创建文件夹 + 写入
            return _install_single_file(
                response.text, url, skill_name, skills_dir
            )

    except httpx.TimeoutException:
        return f"下载超时: {url}"
    except Exception as e:
        agent_logger.error(f"install_skill error: {e}")
        return f"安装失败: {str(e)}"


def _normalize_github_url(url: str) -> str:
    """将 GitHub 仓库页面 URL 自动转换为 ZIP 下载链接"""
    # https://github.com/user/repo → https://github.com/user/repo/archive/refs/heads/main.zip
    # https://github.com/user/repo/tree/main/some/path → ...
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+)(/.+))?",
        url,
    )
    if match:
        owner, repo = match.group(1), match.group(2)
        branch = match.group(3) or "main"
        # 不转换已经是 zip 链接的 URL
        if not url.endswith((".zip", ".tar.gz", ".tgz")):
            return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    return url


def _extract_skill_name(url: str) -> str:
    """从 URL 提取 skill 名称"""
    # 去掉查询参数
    path_part = url.split("?")[0].rstrip("/")

    # GitHub archive: .../repo/archive/... → repo
    match = re.search(r"github\.com/[^/]+/([^/]+)", path_part)
    if match:
        return match.group(1).replace(".git", "")

    # 文件名
    filename = path_part.split("/")[-1]
    name = re.sub(r"\.(zip|tar\.gz|tgz|md|txt|markdown)$", "", filename, flags=re.IGNORECASE)
    return name or "downloaded_skill"


def _is_archive(url: str, content_type: str) -> bool:
    """判断是否为压缩包"""
    archive_extensions = (".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar")
    archive_types = (
        "application/zip",
        "application/x-zip-compressed",
        "application/gzip",
        "application/x-gzip",
        "application/x-tar",
        "application/x-bzip2",
        "application/octet-stream",
    )

    if any(url.lower().endswith(ext) for ext in archive_extensions):
        return True
    if any(t in content_type for t in archive_types):
        # 再检查是否有 .md 在 URL 中（单文件情况）
        if ".md" in url.lower() or ".txt" in url.lower():
            return False
        return True
    return False


def _install_from_archive(
    data: bytes,
    url: str,
    content_type: str,
    skill_name: str,
    skills_dir: Path,
) -> str:
    """从压缩包安装 Skill 文件夹"""
    skill_dir = skills_dir / skill_name

    files_installed = []

    try:
        # 尝试 ZIP
        if url.lower().endswith(".zip") or "zip" in content_type:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # 找到 SKILL.md 所在的根目录前缀
                skill_md_paths = [
                    n for n in zf.namelist()
                    if n.endswith("SKILL.md") or n.endswith("SKILL.MD")
                ]

                if not skill_md_paths:
                    # 没有 SKILL.md，提取所有有意义的文件
                    _extract_all_files(zf, skill_dir, files_installed)
                else:
                    # 找到 SKILL.md 所在的目录前缀
                    prefix = "/".join(skill_md_paths[0].split("/")[:-1]) + "/"
                    if prefix == "/":
                        prefix = ""

                    for member in zf.namelist():
                        # 跳过目录和隐藏文件
                        if member.endswith("/") or "/__MACOSX/" in member:
                            continue
                        # 提取相对于 skill 根目录的路径
                        if prefix and member.startswith(prefix):
                            rel_path = member[len(prefix):]
                        else:
                            # GitHub 归档通常有一层目录，跳过它
                            parts = member.split("/", 1)
                            if len(parts) > 1:
                                rel_path = parts[1]
                            else:
                                rel_path = parts[0]

                        if rel_path:
                            _write_member(zf, member, skill_dir / rel_path, files_installed)
        else:
            # 尝试 tar.gz
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                for member in tf.getmembers():
                    if member.isfile() and not member.name.startswith("."):
                        parts = member.name.split("/", 1)
                        rel_path = parts[1] if len(parts) > 1 else parts[0]
                        if rel_path:
                            file_obj = tf.extractfile(member)
                            if file_obj:
                                target = skill_dir / rel_path
                                target.parent.mkdir(parents=True, exist_ok=True)
                                target.write_bytes(file_obj.read())
                                files_installed.append(str(rel_path))

    except (zipfile.BadZipFile, tarfile.TarError) as e:
        # 压缩包损坏，当作单文件处理
        return _install_single_file(
            data.decode("utf-8", errors="replace"), url, skill_name, skills_dir
        )

    if not files_installed:
        return "警告: 压缩包中未找到有效文件"

    # 安装依赖
    _install_dependencies(skill_dir)

    agent_logger.info(
        f"Skill installed from archive: {skill_name} ({len(files_installed)} files)"
    )
    return (
        f"✅ Skill 安装成功!\n"
        f"名称: {skill_name}\n"
        f"路径: {skill_dir}\n"
        f"文件数: {len(files_installed)}\n"
        f"文件列表:\n" +
        "\n".join(f"  - {f}" for f in files_installed[:20]) +
        (f"\n  ... 共 {len(files_installed)} 个文件" if len(files_installed) > 20 else "") +
        f"\n来源: {url}\n\n"
        f"该 Skill 已可用，Agent 在后续对话中会自动加载。"
    )


def _extract_all_files(zf: zipfile.ZipFile, skill_dir: Path, files_installed: list):
    """提取 ZIP 中所有有意义的文件"""
    for member in zf.namelist():
        if member.endswith("/") or "/__MACOSX/" in member or member.startswith("."):
            continue
        parts = member.split("/", 1)
        rel_path = parts[1] if len(parts) > 1 else parts[0]
        if rel_path:
            _write_member(zf, member, skill_dir / rel_path, files_installed)


def _write_member(zf: zipfile.ZipFile, member: str, target: Path, files_installed: list):
    """写入单个 ZIP 成员"""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src:
        target.write_bytes(src.read())
    files_installed.append(str(target.relative_to(target.parent.parent)))


def _install_single_file(
    content: str,
    url: str,
    skill_name: str,
    skills_dir: Path,
) -> str:
    """安装单个 .md 文件（向后兼容，创建标准文件夹结构）"""
    skill_dir = skills_dir / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    file_path = skill_dir / "SKILL.md"
    file_path.write_text(content, encoding="utf-8")

    agent_logger.info(f"Skill installed (single file): {skill_name} from {url}")
    return (
        f"✅ Skill 安装成功!\n"
        f"名称: {skill_name}\n"
        f"路径: {skill_dir}\n"
        f"文件: SKILL.md ({len(content)} 字符)\n"
        f"来源: {url}\n\n"
        f"注意: 这是一个单文件 Skill。如需脚本和依赖，请提供包含完整 Skill 文件夹的 ZIP 压缩包。\n"
        f"该 Skill 已可用，Agent 在后续对话中会自动加载。"
    )


def _install_dependencies(skill_dir: Path):
    """安装 Skill 的 Python 依赖"""
    req_file = skill_dir / "requirements.txt"
    if req_file.exists():
        try:
            import subprocess
            result = subprocess.run(
                ["pip", "install", "-r", str(req_file), "-q"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                agent_logger.info(f"Skill dependencies installed from {req_file}")
            else:
                agent_logger.warning(f"Dependency install failed: {result.stderr[:200]}")
        except Exception as e:
            agent_logger.warning(f"Dependency install error: {e}")
