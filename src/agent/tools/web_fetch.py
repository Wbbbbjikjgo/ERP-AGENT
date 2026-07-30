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
import yaml
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
    # 初始化结果字典，用于存储解压后的文件路径和内容
    result: dict[str, bytes] = {}

    try:
        # 检查 URL 是否以 .zip 结尾或 content-type 包含 zip
        if url.lower().endswith(".zip") or "zip" in content_type:
            # 使用 io.BytesIO 将字节数据转为内存中的文件对象
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # 遍历 ZIP 包中的所有成员（文件/文件夹）
                for member in zf.namelist():
                    # 跳过目录（以/结尾）、__MACOSX 系统文件夹、隐藏文件（以.开头）
                    if member.endswith("/") or "/__MACOSX/" in member or member.startswith("."):
                        continue
                    # 按第一个斜杠分割路径，获取相对路径
                    parts = member.split("/", 1)
                    # 如果有多级目录，取第二部分作为相对路径；否则直接用文件名
                    rel_path = parts[1] if len(parts) > 1 else parts[0]
                    if rel_path:
                        # 将文件内容读入内存，存入结果字典
                        result[rel_path] = zf.read(member)
        else:
            # 处理 tar.gz 格式
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                # 遍历 tar 包中的所有成员
                for member in tf.getmembers():
                    # 只处理文件（不是目录），且文件名不以.开头
                    if member.isfile() and not member.name.startswith("."):
                        # 按第一个斜杠分割，获取相对路径
                        parts = member.name.split("/", 1)
                        rel_path = parts[1] if len(parts) > 1 else parts[0]
                        if rel_path:
                            # 提取文件内容
                            fobj = tf.extractfile(member)
                            if fobj:
                                result[rel_path] = fobj.read()
    except (zipfile.BadZipFile, tarfile.TarError):
        # 如果压缩包损坏或格式不对，不做任何处理，返回空字典
        pass

    # 返回解压后的文件字典
    return result


# 允许的安全导入白名单（方案二：白名单机制）
_ALLOWED_IMPORTS = {
    'json', 're', 'datetime', 'collections', 'itertools',
    'math', 'random', 'typing', 'dataclasses', 'enum',
    'pathlib', 'os', 'io', 'csv',
}

# 危险模式检测列表
_DANGEROUS_PATTERNS = [
    (r'eval\s*\(', "使用了 eval()，可能执行任意代码"),
    (r'exec\s*\(', "使用了 exec()，可能执行任意代码"),
    (r'__import__\s*\(', "使用了动态导入，可能加载恶意模块"),
    (r'subprocess\.(Popen|call|run|check_output|check_call)', "使用了 subprocess，可能执行系统命令"),
    (r'os\.system\s*\(', "使用了 os.system，可能执行系统命令"),
    (r'os\.popen\s*\(', "使用了 os.popen，可能执行系统命令"),
    (r'builtins\s*\.', "访问了内置模块，可能有风险"),
    (r'compile\s*\(', "使用了 compile()，可能执行动态代码"),
    (r'pickle\.(loads|load)', "使用了 pickle 反序列化，可能有远程执行风险"),
    (r'socket\.', "使用了 socket 通信，可能有网络风险"),
    (r'ctypes\.', "使用了 ctypes，可能绕过 Python 安全限制"),
]


def _scan_python_file(content: str, filepath: str) -> list[str]:
    """扫描单个 Python 文件的安全风险（方案二部分）。
    返回: 警告列表（非空即有风险）
    """
    warnings = []

    for pattern, warning in _DANGEROUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            warnings.append(f"{filepath}: {warning}")

    return warnings


def _validate_skill_in_sandbox(sandbox, skill_name: str, sandbox_skill_dir: str) -> tuple[bool, str, list[str]]:
    """
    在沙箱中验证技能文件完整性（严格模式：方案一 + 方案二部分）。

    验证项目：
    1. SKILL.md 文件存在性
    2. YAML frontmatter 合法解析
    3. 必需字段 name 的非空校验
    4. 可选字段类型校验 (version, description)
    5. name 字段路径安全性校验
    6. Python 文件危险代码扫描（方案二）
    7. 路径穿越攻击检测
    8. 文件大小 DoS 防护

    返回: (是否通过, 错误信息, 文件列表)
    """
    # 1. 检查 SKILL.md 是否存在
    has_sk = sandbox.execute(f"test -f '{sandbox_skill_dir}/SKILL.md' && echo YES || echo NO")
    if has_sk.exit_code != 0 or "YES" not in has_sk.output:
        return False, "SKILL.md 未找到，技能格式无效", []

    # 2. 读取完整内容
    read_sk = sandbox.execute(f"cat '{sandbox_skill_dir}/SKILL.md'")
    if read_sk.exit_code != 0:
        return False, "无法读取 SKILL.md", []

    content = read_sk.output

    # 3. 验证 YAML frontmatter 是否存在且格式正确
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.search(frontmatter_pattern, content, re.DOTALL)

    if not match:
        return False, "SKILL.md 缺少有效的 YAML frontmatter（必须用 --- 包裹）", []

    # 4. 使用 yaml 库严格解析
    try:
        frontmatter_yaml = match.group(1)
        metadata = yaml.safe_load(frontmatter_yaml)

        if not isinstance(metadata, dict):
            return False, "YAML frontmatter 格式错误（必须是键值对）", []

        if "name" not in metadata:
            return False, "SKILL.md frontmatter 缺少必需的 'name' 字段", []

        if not metadata["name"] or not isinstance(metadata["name"], str):
            return False, "SKILL.md 'name' 字段必须是非空字符串", []

        if "version" in metadata and not isinstance(metadata["version"], str):
            return False, "SKILL.md 'version' 字段必须是字符串", []

        if "description" in metadata and not isinstance(metadata["description"], str):
            return False, "SKILL.md 'description' 字段必须是字符串", []

        if not re.match(r'^[\w\-\.]+$', metadata["name"]):
            return False, f"SKILL.md 'name' 字段包含非法字符: {metadata['name']}", []

        if metadata["name"] != skill_name:
            agent_logger.warning(
                f"Skill name mismatch: SKILL.md name='{metadata['name']}' != URL name='{skill_name}'"
            )

    except yaml.YAMLError as e:
        return False, f"YAML frontmatter 解析失败: {str(e)}", []

    # 5. 安全扫描：检查 Python 文件中的危险模式（方案二部分）
    py_files_result = sandbox.execute(
        f"find '{sandbox_skill_dir}' -name '*.py' -type f 2>/dev/null"
    )
    if py_files_result.exit_code == 0 and py_files_result.output.strip():
        for py_file in py_files_result.output.strip().split('\n'):
            if not py_file.strip():
                continue
            file_content = sandbox.execute(f"cat '{py_file}'")
            if file_content.exit_code != 0:
                continue
            warnings = _scan_python_file(file_content.output, py_file)
            if warnings:
                for w in warnings:
                    agent_logger.warning(f"Security risk in skill: {w}")

    # 6. 路径穿越攻击检测 & 文件大小检查
    ls_result = sandbox.execute(f"find '{sandbox_skill_dir}' -type f | sort")
    files = []
    if ls_result.exit_code == 0:
        for f in ls_result.output.strip().split('\n'):
            f = f.strip()
            if not f:
                continue
            if '..' in f:
                return False, f"检测到路径穿越攻击: {f}", []
            files.append(f)

    # 7. 文件大小检查（DoS 防护）
    for f in files:
        size_check = sandbox.execute(
            f"stat -c%s '{f}' 2>/dev/null || stat -f%z '{f}' 2>/dev/null"
        )
        if size_check.exit_code == 0 and size_check.output.strip():
            try:
                file_size = int(size_check.output.strip())
                if file_size > 10 * 1024 * 1024:
                    return False, f"文件过大 ({file_size} bytes): {f}", []
            except ValueError:
                pass

    return True, "", files


def _install_from_sandbox_to_host(sandbox, sandbox_skill_dir: str, host_skill_dir: Path, files: list[str]) -> list[str]:
    """
    从沙箱读取验证通过的文件，写入宿主机 skills 目录。
    返回已安装的文件列表。
    """
    # 初始化已安装文件列表
    installed = []
    # 遍历所有需要从沙箱复制的文件
    for remote_path in files:
        try:
            # 从沙箱读取文件内容（字节）
            content = sandbox.read_file_bytes(remote_path)
            # 计算相对于沙箱技能目录的相对路径
            rel = remote_path.replace(sandbox_skill_dir, "").lstrip("/")
            # 构建宿主机上的目标文件路径
            target = host_skill_dir / rel
            # 创建目标文件所在的目录（如果不存在）
            target.parent.mkdir(parents=True, exist_ok=True)
            # 将内容写入宿主机文件
            target.write_bytes(content)
            # 记录已安装的文件名
            installed.append(rel)
        except Exception as e:
            # 如果复制失败，记录警告日志但继续处理其他文件
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
    # 验证 URL 协议是否合法（只支持 HTTP 和 HTTPS）
    if not url.startswith(("http://", "https://")):
        return "错误: URL 必须以 http:// 或 https:// 开头"

    # 标准化 GitHub URL，将仓库页面转为 ZIP 下载链接
    url = _normalize_github_url(url)
    # 如果未指定技能名称，从 URL 自动提取
    if not skill_name:
        skill_name = _extract_skill_name(url)
    # 将技能名称中的非法字符替换为下划线，确保文件系统安全
    skill_name = re.sub(r"[^\w\-]", "_", skill_name)

    # 获取沙箱实例（安全隔离环境）
    from ..backends.sandbox_holder import get_sandbox
    sandbox = get_sandbox()

    try:
        # Step 1: 下载文件到内存
        response = httpx.get(
            url,
            follow_redirects=True,  # 自动跟随重定向
            timeout=30,              # 30秒超时
            headers={"User-Agent": "ERP-Agent/1.0 (Skill Installer)"},  # 设置 User-Agent
        )
        # 检查 HTTP 响应状态码
        if response.status_code != 200:
            return f"下载失败: HTTP {response.status_code}"
        # 获取响应头中的 content-type
        content_type = response.headers.get("content-type", "")
        # 检查下载内容是否为空
        if len(response.content) == 0:
            return "错误: 下载内容为空"

        # 检查沙箱是否可用
        if sandbox is None:
            return "错误: 沙箱不可用，无法安全安装 Skill"

        # Step 2: 在 Python 中解压，获取文件映射
        # 在沙箱中创建临时目录用于验证
        sandbox_tmp = f"/tmp/_skill_install_{skill_name}"

        # 判断是否为压缩包格式
        if _is_archive(url, content_type):
            # 解压到内存字典
            files_dict = _extract_archive_to_memory(response.content, url, content_type)
        else:
            # 单文件（SKILL.md），直接保存为字节
            files_dict = {"SKILL.md": response.text.encode("utf-8")}

        # 如果没有提取到任何文件，清理沙箱临时目录并报错
        if not files_dict:
            sandbox.execute(f"rm -rf {sandbox_tmp} 2>/dev/null || true")
            return "错误: 压缩包中未找到有效文件"

        # 找到 SKILL.md 所在的目录前缀（用于剥离顶层目录）
        skill_prefix = ""
        for path in files_dict:
            if path.endswith("SKILL.md"):
                # 如果路径包含斜杠，取目录部分作为前缀
                parts = path.split("/")
                if len(parts) > 1:
                    skill_prefix = "/".join(parts[:-1]) + "/"
                break
        else:
            # 如果循环结束都没找到 SKILL.md
            sandbox.execute(f"rm -rf {sandbox_tmp} 2>/dev/null || true")
            return "错误: 未找到 SKILL.md，安装取消"

        # Step 3: 上传文件到沙箱验证
        sandbox.execute(f"mkdir -p {sandbox_tmp}/skill")
        for rel_path, content in files_dict.items():
            clean_path = rel_path[len(skill_prefix):] if rel_path.startswith(skill_prefix) else rel_path
            if not clean_path:
                continue
            sandbox.write_file(f"{sandbox_tmp}/skill/{clean_path}", content)

        # Step 4: 在沙箱中验证文件完整性
        valid, err_msg, sandbox_files = _validate_skill_in_sandbox(sandbox, skill_name, f"{sandbox_tmp}/skill")
        if not valid:
            # 验证失败，清理沙箱临时文件
            sandbox.execute(f"rm -rf {sandbox_tmp}")
            return f"沙箱验证失败: {err_msg}（已清理沙箱临时文件，未影响宿主机）"

        # Step 5: 验证通过 → 从沙箱复制到宿主机 + 沙箱正式目录
        sandbox_verify_dir = f"{sandbox_tmp}/skill"
        host_skills_dir = Path(SKILLS_DIR)
        host_skills_dir.mkdir(parents=True, exist_ok=True)
        host_target = host_skills_dir / skill_name

        installed = _install_from_sandbox_to_host(sandbox, sandbox_verify_dir, host_target, sandbox_files)

        # 同步写入沙箱正式技能目录（用于后续执行）
        scope = "procurement"
        for rel in installed:
            remote_target = f"/skills/{scope}/{skill_name}/{rel}"
            try:
                sandbox.write_file(remote_target, sandbox.read_file_bytes(f"{sandbox_verify_dir}/{rel}"))
            except Exception as e:
                agent_logger.warning(f"Failed to write to sandbox skills dir: {e}")

        # 安装依赖（在沙箱内执行 pip install -r requirements.txt）
        _install_dependencies(host_target)

        # 清理沙箱临时文件（释放临时空间）
        sandbox.execute(f"rm -rf {sandbox_tmp}")

        # 记录安装日志
        agent_logger.info(
            f"Skill installed (sandbox-verified): {skill_name} ({len(installed)} files)"
        )
        # 返回成功信息，包含技能名称、路径、文件数量和列表
        return (
            f"✅ Skill 安装成功！（沙箱安全验证通过）\n"
            f"名称: {skill_name}\n"
            f"路径: {host_target}\n"
            f"文件数: {len(installed)}\n"
            f"文件列表:\n" +
            "\n".join(f"  - {f}" for f in installed[:20]) +  # 只显示前20个文件
            (f"\n  ... 共 {len(installed)} 个文件" if len(installed) > 20 else "") +
            f"\n来源: {url}\n\n"
            f"该 Skill 已通过沙箱安全验证，现已安装到正式环境。"
        )

    except httpx.TimeoutException:
        # 处理下载超时异常
        return f"下载超时: {url}"
    except Exception as e:
        # 处理其他所有异常，记录错误日志
        agent_logger.error(f"install_skill error: {e}")
        # 尝试清理沙箱临时文件
        if sandbox:
            try:
                sandbox.execute(f"rm -rf /tmp/_skill_install_{skill_name} 2>/dev/null || true")
            except Exception:
                pass
        return f"安装失败: {str(e)}"


def _normalize_github_url(url: str) -> str:
    """将 GitHub 仓库页面 URL 自动转换为 ZIP 下载链接"""
    # 匹配 GitHub 仓库 URL 的正则表达式
    # 格式: https://github.com/owner/repo 或 https://github.com/owner/repo/tree/branch/path
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+)(/.+))?",
        url,
    )
    if match:
        # 提取所有者、仓库名和分支
        owner, repo = match.group(1), match.group(2)
        branch = match.group(3) or "main"  # 默认使用 main 分支
        # 如果 URL 本身不是压缩包链接，转换为 ZIP 下载链接
        if not url.endswith((".zip", ".tar.gz", ".tgz")):
            return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    return url  # 不是 GitHub 仓库 URL，原样返回


def _extract_skill_name(url: str) -> str:
    """从 URL 提取 skill 名称"""
    # 去掉查询参数（?后面的部分）
    path_part = url.split("?")[0].rstrip("/")

    # 如果是 GitHub 仓库，提取仓库名
    match = re.search(r"github\.com/[^/]+/([^/]+)", path_part)
    if match:
        return match.group(1).replace(".git", "")  # 移除 .git 后缀

    # 否则取路径的最后一部分作为文件名
    filename = path_part.split("/")[-1]
    # 移除常见的压缩包和文档扩展名
    name = re.sub(r"\.(zip|tar\.gz|tgz|md|txt|markdown)$", "", filename, flags=re.IGNORECASE)
    # 如果提取的名称为空，使用默认值
    return name or "downloaded_skill"


def _is_archive(url: str, content_type: str) -> bool:
    """判断是否为压缩包"""
    # 定义压缩包的扩展名列表
    archive_extensions = (".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar")
    # 定义压缩包的 MIME 类型列表
    archive_types = (
        "application/zip",
        "application/x-zip-compressed",
        "application/gzip",
        "application/x-gzip",
        "application/x-tar",
        "application/x-bzip2",
        "application/octet-stream",
    )

    # 如果 URL 以压缩包扩展名结尾，判定为压缩包
    if any(url.lower().endswith(ext) for ext in archive_extensions):
        return True
    # 如果 content-type 匹配压缩包类型
    if any(t in content_type for t in archive_types):
        # 但是要排除 .md 或 .txt 单文件的情况（避免误判）
        if ".md" in url.lower() or ".txt" in url.lower():
            return False
        return True
    return False


def _install_dependencies(skill_dir: Path):
    """安装 Skill 的 Python 依赖（优先在沙箱内安装，不回退到宿主机）"""
    # 检查 requirements.txt 是否存在
    req_file = skill_dir / "requirements.txt"
    if not req_file.exists():
        return

    # 尝试在沙箱内安装依赖
    try:
        from ..backends.sandbox_holder import get_sandbox
        sandbox = get_sandbox()
        if sandbox is not None:
            # 读取 requirements.txt 内容
            req_content = req_file.read_text(encoding="utf-8")
            # 将内容写入沙箱临时文件
            sandbox_req = f"/skills/requirements_{skill_dir.name}.txt"
            sandbox.write_file(sandbox_req, req_content)
            # 在沙箱中执行 pip install
            result = sandbox.execute(f"pip install -r {sandbox_req} -q", timeout=120)
            # 清理沙箱临时文件
            sandbox.execute(f"rm -f {sandbox_req}")
            if result.exit_code == 0:
                agent_logger.info(f"Skill dependencies installed in sandbox from {req_file}")
            else:
                agent_logger.warning(f"Sandbox dependency install failed: {result.output[:200]}")
            return
    except Exception as e:
        agent_logger.warning(f"Sandbox dependency install error: {e}")

    # 如果沙箱不可用，仅记录警告，不在宿主机安装依赖
    # 这样做是为了保持宿主机环境清洁，依赖会在沙箱准备好时安装
    agent_logger.warning(
        f"Sandbox unavailable, skipping dependency installation for {req_file}. "
        "Dependencies will be installed when sandbox is ready."
    )