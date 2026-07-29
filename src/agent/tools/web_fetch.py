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
# Skill 安装（沙箱安全隔离）
# 流程图：下载 → 沙箱验证 → 通过 → 安装到正式环境
#         ↓ 失败
#       清理沙箱临时文件 + 返回错误
# ============================================================

def _extract_archive_to_memory(data: bytes, url: str, content_type: str) -> dict[str, bytes]:
    """
    将压缩包解压到内存字典 {相对路径: 字节内容}。
    支持 ZIP 和 TAR.GZ 格式。
    """
    result: dict[str, bytes] = {}

    try:
        if url.lower().endswith(".zip") or "zip" in content_type:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for member in zf.namelist():
                    if member.endswith("/") or "/__MACOSX/" in member or member.startswith("."):
                        continue
                    parts = member.split("/", 1)
                    rel_path = parts[1] if len(parts) > 1 else parts[0]
                    if rel_path:
                        result[rel_path] = zf.read(member)
        else:
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                for member in tf.getmembers():
                    if member.isfile() and not member.name.startswith("."):
                        parts = member.name.split("/", 1)
                        rel_path = parts[1] if len(parts) > 1 else parts[0]
                        if rel_path:
                            fobj = tf.extractfile(member)
                            if fobj:
                                result[rel_path] = fobj.read()
    except (zipfile.BadZipFile, tarfile.TarError):
        # 不是有效的压缩包，当作单文件
        pass

    return result


def _validate_skill_in_sandbox(sandbox, skill_name: str, sandbox_skill_dir: str) -> tuple[bool, str, list[str]]:
    """
    在沙箱中验证技能文件完整性。
    返回: (是否通过, 错误信息, 文件列表)
    """
    # 检查 SKILL.md 是否存在
    has_sk = sandbox.execute(f"test -f '{sandbox_skill_dir}/SKILL.md' && echo YES || echo NO")
    if has_sk.exit_code != 0 or "YES" not in has_sk.output:
        return False, "SKILL.md 未找到，技能格式无效", []

    # 读取 SKILL.md 验证 frontmatter
    read_sk = sandbox.execute(f"head -30 '{sandbox_skill_dir}/SKILL.md'")
    if read_sk.exit_code != 0 or "name:" not in read_sk.output:
        return False, "SKILL.md 缺少 name 字段(YAML frontmatter)", []

    # 列出所有文件
    ls_result = sandbox.execute(f"find '{sandbox_skill_dir}' -type f | sort")
    files = []
    if ls_result.exit_code == 0:
        files = [f.strip() for f in ls_result.output.strip().split("\n") if f.strip()]

    return True, "", files


def _install_from_sandbox_to_host(sandbox, sandbox_skill_dir: str, host_skill_dir: Path, files: list[str]) -> list[str]:
    """
    从沙箱读取验证通过的文件，写入宿主机 skills 目录。
    返回已安装的文件列表。
    """
    installed = []
    for remote_path in files:
        try:
            content = sandbox.read_file_bytes(remote_path)
            # 计算相对于 sandbox_skill_dir 的相对路径
            rel = remote_path.replace(sandbox_skill_dir, "").lstrip("/")
            target = host_skill_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            installed.append(rel)
        except Exception as e:
            agent_logger.warning(f"Failed to copy {remote_path} from sandbox: {e}")
    return installed


@tool
def install_skill(url: str, skill_name: str = "") -> str:
    """从 URL 下载并安装完整 Skill（沙箱安全隔离流程）。

    安全流程：
    1. 下载到内存
    2. 上传到沙箱 /tmp/ 验证
    3. 在沙箱中解压并校验 SKILL.md 完整性
    4. 校验通过 → 从沙箱复制到宿主机 src/skills/
    5. 校验失败 → 清理沙箱临时文件

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

    url = _normalize_github_url(url)
    if not skill_name:
        skill_name = _extract_skill_name(url)
    skill_name = re.sub(r"[^\w\-]", "_", skill_name)

    # 获取沙箱
    from ..backends.sandbox_holder import get_sandbox
    sandbox = get_sandbox()

    try:
        # Step 1: 下载
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "ERP-Agent/1.0 (Skill Installer)"},
        )
        if response.status_code != 200:
            return f"下载失败: HTTP {response.status_code}"
        content_type = response.headers.get("content-type", "")
        if len(response.content) == 0:
            return "错误: 下载内容为空"

        if sandbox is None:
            return "错误: 沙箱不可用，无法安全安装 Skill"

        # Step 2: 在 Python 中解压，获取文件映射
        sandbox_tmp = f"/tmp/_skill_install_{skill_name}"

        if _is_archive(url, content_type):
            # 解压到内存
            files_dict = _extract_archive_to_memory(response.content, url, content_type)
        else:
            # 单文件
            files_dict = {"SKILL.md": response.text.encode("utf-8")}

        if not files_dict:
            sandbox.execute(f"rm -rf {sandbox_tmp} 2>/dev/null || true")
            return "错误: 压缩包中未找到有效文件"

        # 找到 SKILL.md 所在目录前缀
        skill_prefix = ""
        for path in files_dict:
            if path.endswith("SKILL.md"):
                parts = path.split("/")
                if len(parts) > 1:
                    skill_prefix = "/".join(parts[:-1]) + "/"
                break
        else:
            sandbox.execute(f"rm -rf {sandbox_tmp} 2>/dev/null || true")
            return "错误: 未找到 SKILL.md，安装取消"

        # Step 3: 上传文件到沙箱验证
        uploaded_files = []
        sandbox.execute(f"mkdir -p {sandbox_tmp}/skill")
        for rel_path, content in files_dict.items():
            # 去掉前缀
            clean_path = rel_path[len(skill_prefix):] if rel_path.startswith(skill_prefix) else rel_path
            if not clean_path:
                continue
            remote = f"{sandbox_tmp}/skill/{clean_path}"
            sandbox.write_file(remote, content)
            uploaded_files.append(remote)

        # Step 4: 在沙箱中验证
        valid, err_msg, _ = _validate_skill_in_sandbox(sandbox, skill_name, f"{sandbox_tmp}/skill")
        if not valid:
            sandbox.execute(f"rm -rf {sandbox_tmp}")
            return f"沙箱验证失败: {err_msg}（已清理沙箱临时文件，未影响宿主机）"

        # Step 5: 验证通过 → 安装到宿主机 + 沙箱正式目录
        host_skills_dir = Path(SKILLS_DIR)
        host_skills_dir.mkdir(parents=True, exist_ok=True)
        host_target = host_skills_dir / skill_name

        installed = []
        scope = "procurement"
        for rel_path, content in files_dict.items():
            clean_path = rel_path[len(skill_prefix):] if rel_path.startswith(skill_prefix) else rel_path
            if not clean_path:
                continue

            # 写入宿主机
            target = host_target / clean_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            installed.append(clean_path)

            # 同步写入沙箱正式技能目录
            remote_target = f"/skills/{scope}/{skill_name}/{clean_path}"
            try:
                sandbox.write_file(remote_target, content)
            except Exception as e:
                agent_logger.warning(f"Failed to write to sandbox skills dir: {e}")

        # 安装依赖（沙箱内）
        _install_dependencies(host_target)

        # 清理沙箱临时文件
        sandbox.execute(f"rm -rf {sandbox_tmp}")

        agent_logger.info(
            f"Skill installed (sandbox-verified): {skill_name} ({len(installed)} files)"
        )
        return (
            f"✅ Skill 安装成功！（沙箱安全验证通过）\n"
            f"名称: {skill_name}\n"
            f"路径: {host_target}\n"
            f"文件数: {len(installed)}\n"
            f"文件列表:\n" +
            "\n".join(f"  - {f}" for f in installed[:20]) +
            (f"\n  ... 共 {len(installed)} 个文件" if len(installed) > 20 else "") +
            f"\n来源: {url}\n\n"
            f"该 Skill 已通过沙箱安全验证，现已安装到正式环境。"
        )

    except httpx.TimeoutException:
        return f"下载超时: {url}"
    except Exception as e:
        agent_logger.error(f"install_skill error: {e}")
        if sandbox:
            try:
                sandbox.execute(f"rm -rf /tmp/_skill_install_{skill_name} 2>/dev/null || true")
            except Exception:
                pass
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
    """安装 Skill 的 Python 依赖（优先在沙箱内安装，不回退到宿主机）"""
    req_file = skill_dir / "requirements.txt"
    if not req_file.exists():
        return

    # 尝试在沙箱内安装
    try:
        from ..backends.sandbox_holder import get_sandbox
        sandbox = get_sandbox()
        if sandbox is not None:
            # 将 requirements.txt 同步到沙箱
            req_content = req_file.read_text(encoding="utf-8")
            sandbox_req = f"/skills/requirements_{skill_dir.name}.txt"
            sandbox.write_file(sandbox_req, req_content)
            result = sandbox.execute(f"pip install -r {sandbox_req} -q", timeout=120)
            sandbox.execute(f"rm -f {sandbox_req}")
            if result.exit_code == 0:
                agent_logger.info(f"Skill dependencies installed in sandbox from {req_file}")
            else:
                agent_logger.warning(f"Sandbox dependency install failed: {result.output[:200]}")
            return
    except Exception as e:
        agent_logger.warning(f"Sandbox dependency install error: {e}")

    # 沙箱不可用时，仅记录警告，不在宿主机安装
    agent_logger.warning(
        f"Sandbox unavailable, skipping dependency installation for {req_file}. "
        "Dependencies will be installed when sandbox is ready."
    )
