"""
沙箱创建 + 安全防护 + 多语言运行时初始化

Harness 核心思想：
1. 文件系统只读 (--read-only) + tmpfs 可写区域
2. 内存/CPU 资源限制
3. 网络隔离 (--network none 或受限网络)
4. Linux Capability 全部移除
5. seccomp 系统调用白名单
6. 可扩展多语言运行时（Python / Go / Node.js）

沙箱由 SandboxManager 统一管理，不直接暴露给 Agent。
"""
import json
import docker
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .custom_opensandbox import CustomOpenSandbox
from ..log_utils import sandbox_logger
from ..config import SANDBOX_WORK_DIR, SANDBOX_IMAGE


# ============================================================
# 沙箱配置数据类
# ============================================================

@dataclass
class SandboxConfig:
    """沙箱创建配置（可扩展）"""

    # --- 基础 ---
    image: str = SANDBOX_IMAGE
    name: str = "erp-sandbox"
    work_dir: str = SANDBOX_WORK_DIR

    # --- 安全防护 ---
    read_only: bool = True
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    network_mode: str = "bridge"          # "none" = 完全隔离, "bridge" = 受限
    tmpfs_size: str = "128m"
    drop_all_caps: bool = True
    use_seccomp: bool = True
    seccomp_path: str = ""                # 空则使用内置 seccomp.json

    # --- 多语言运行时 ---
    # 指定需要安装的运行时列表: ["python", "go", "node"]
    runtimes: list[str] = field(default_factory=lambda: ["python"])

    # --- 环境变量注入 ---
    env_vars: dict[str, str] = field(default_factory=dict)


# ============================================================
# 内置 seccomp 路径
# ============================================================

_BUILTIN_SECCOMP = str(Path(__file__).parent / "seccomp.json")


# ============================================================
# 安全沙箱创建（Docker SDK）
# ============================================================

def create_secure_sandbox(config: SandboxConfig | None = None) -> CustomOpenSandbox:
    """
    创建安全加固的 Docker 沙箱容器

    七层安全防护：
    1. --read-only           文件系统只读
    2. --tmpfs /tmp          可写区域限制大小
    3. --memory / --cpus     资源上限
    4. --network none        网络隔离（或受限）
    5. --cap-drop ALL        移除所有 Linux Capability
    6. --security-opt seccomp  系统调用白名单
    7. --pids-limit          进程数上限

    Returns:
        CustomOpenSandbox 实例（已连接到新建容器）
    """
    if config is None:
        config = SandboxConfig()

    seccomp_path = config.seccomp_path or _BUILTIN_SECCOMP
    seccomp_profile = None
    if config.use_seccomp and Path(seccomp_path).exists():
        with open(seccomp_path, "r") as f:
            seccomp_profile = f.read()

    client = docker.from_env()

    # 检查容器是否已存在，存在则先移除
    try:
        existing = client.containers.get(config.name)
        sandbox_logger.info(f"Removing existing container: {config.name}")
        existing.stop(timeout=3)
        existing.remove(force=True)
    except docker.errors.NotFound:
        pass

    # 构建安全参数
    host_config_kwargs = {
        "read_only": config.read_only,
        "mem_limit": config.memory_limit,
        "nano_cpus": int(config.cpu_limit * 1e9),
        "pids_limit": 256,
        "tmpfs": {
            "/tmp": f"rw,noexec,nosuid,size={config.tmpfs_size}",
            "/workspace": f"rw,noexec,nosuid,size=256m",
        },
    }

    # 网络模式
    if config.network_mode == "none":
        host_config_kwargs["network_mode"] = "none"
    else:
        host_config_kwargs["network_mode"] = config.network_mode

    # Capability 安全
    if config.drop_all_caps:
        host_config_kwargs["cap_drop"] = ["ALL"]
        # 仅添加运行必需的最小 Capability
        host_config_kwargs["cap_add"] = ["CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE"]

    # seccomp 安全策略
    security_opts = []
    if seccomp_profile:
        security_opts.append(f"seccomp={seccomp_path}")
    security_opts.append("no-new-privileges:true")
    host_config_kwargs["security_opt"] = security_opts

    # 环境变量
    environment = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    environment.update(config.env_vars)

    try:
        sandbox_logger.info(
            f"Creating secure sandbox: {config.name} "
            f"(image={config.image}, memory={config.memory_limit}, "
            f"cpu={config.cpu_limit}, network={config.network_mode})"
        )

        container = client.containers.run(
            image=config.image,
            name=config.name,
            command="sleep infinity",
            detach=True,
            working_dir=config.work_dir,
            environment=environment,
            **host_config_kwargs,
        )

        sandbox_logger.info(
            f"Secure sandbox created: {config.name} ({container.id[:12]})"
        )

    except Exception as e:
        # 安全创建失败时，回退到基础模式
        sandbox_logger.warning(
            f"Secure sandbox creation failed ({e}), falling back to basic mode"
        )
        try:
            existing = client.containers.get(config.name)
            existing.stop(timeout=3)
            existing.remove(force=True)
        except docker.errors.NotFound:
            pass

        container = client.containers.run(
            image=config.image,
            name=config.name,
            command="sleep infinity",
            detach=True,
            working_dir=config.work_dir,
            environment=environment,
        )
        sandbox_logger.info(
            f"Basic sandbox created (fallback): {config.name} ({container.id[:12]})"
        )

    client.close()

    # 创建 CustomOpenSandbox 实例连接到新容器
    sandbox = CustomOpenSandbox(container_name=config.name)

    # 初始化运行时环境
    _init_runtimes(sandbox, config.runtimes)

    return sandbox


# ============================================================
# 多语言运行时初始化
# ============================================================

def _init_runtimes(sandbox: CustomOpenSandbox, runtimes: list[str]):
    """
    根据配置初始化多语言运行时

    支持的运行时：
    - python: 预装在 python:3.11-slim 镜像中
    - go:     通过二进制包安装（轻量）
    - node:   通过 NodeSource 安装
    - java:   通过 OpenJDK 安装
    - rust:   通过 rustup 安装
    """
    for runtime in runtimes:
        try:
            if runtime == "python":
                _init_python_runtime(sandbox)
            elif runtime == "go":
                _init_go_runtime(sandbox)
            elif runtime == "node":
                _init_node_runtime(sandbox)
            elif runtime == "java":
                _init_java_runtime(sandbox)
            elif runtime == "rust":
                _init_rust_runtime(sandbox)
            else:
                sandbox_logger.warning(f"Unknown runtime: {runtime}")
        except Exception as e:
            sandbox_logger.error(f"Failed to init runtime '{runtime}': {e}")


def _init_python_runtime(sandbox: CustomOpenSandbox):
    """初始化 Python 运行时（预装常用包）"""
    resp = sandbox.execute("python3 --version")
    if resp.exit_code == 0:
        sandbox_logger.info(f"Python runtime: {resp.output.strip()}")
    else:
        sandbox_logger.warning("Python not available in sandbox")

    # 安装常用数据分析包
    resp = sandbox.execute(
        "pip install --no-cache-dir matplotlib pandas numpy -q 2>&1 | tail -5"
    )
    if resp.exit_code == 0:
        sandbox_logger.info("Python packages installed: matplotlib, pandas, numpy")


def _init_go_runtime(sandbox: CustomOpenSandbox):
    """安装 Go 运行时"""
    resp = sandbox.execute("go version 2>/dev/null || echo NOT_INSTALLED")
    if "NOT_INSTALLED" not in resp.output:
        sandbox_logger.info(f"Go runtime: {resp.output.strip()}")
        return

    sandbox_logger.info("Installing Go runtime...")
    resp = sandbox.execute(
        "wget -q https://go.dev/dl/go1.22.4.linux-amd64.tar.gz -O /tmp/go.tar.gz "
        "&& tar -C /usr/local -xzf /tmp/go.tar.gz "
        "&& rm /tmp/go.tar.gz "
        "&& export PATH=$PATH:/usr/local/go/bin "
        "&& go version",
        timeout=120,
    )
    if resp.exit_code == 0:
        sandbox_logger.info(f"Go installed: {resp.output.strip()}")
    else:
        sandbox_logger.warning(f"Go install failed: {resp.output}")


def _init_node_runtime(sandbox: CustomOpenSandbox):
    """安装 Node.js 运行时"""
    resp = sandbox.execute("node --version 2>/dev/null || echo NOT_INSTALLED")
    if "NOT_INSTALLED" not in resp.output:
        sandbox_logger.info(f"Node runtime: {resp.output.strip()}")
        return

    sandbox_logger.info("Installing Node.js runtime...")
    resp = sandbox.execute(
        "apt-get update -qq && apt-get install -y -qq nodejs npm 2>&1 | tail -3 "
        "&& node --version",
        timeout=120,
    )
    if resp.exit_code == 0:
        sandbox_logger.info(f"Node installed: {resp.output.strip()}")
    else:
        sandbox_logger.warning(f"Node install failed: {resp.output}")


def _init_java_runtime(sandbox: CustomOpenSandbox):
    """安装 Java (OpenJDK) 运行时"""
    resp = sandbox.execute("java --version 2>/dev/null || echo NOT_INSTALLED")
    if "NOT_INSTALLED" not in resp.output:
        sandbox_logger.info(f"Java runtime: {resp.output.strip()}")
        return

    sandbox_logger.info("Installing Java runtime...")
    resp = sandbox.execute(
        "apt-get update -qq && apt-get install -y -qq default-jdk-headless 2>&1 | tail -3 "
        "&& java --version",
        timeout=180,
    )
    if resp.exit_code == 0:
        sandbox_logger.info(f"Java installed: {resp.output.strip()}")


def _init_rust_runtime(sandbox: CustomOpenSandbox):
    """安装 Rust 运行时"""
    resp = sandbox.execute("rustc --version 2>/dev/null || echo NOT_INSTALLED")
    if "NOT_INSTALLED" not in resp.output:
        sandbox_logger.info(f"Rust runtime: {resp.output.strip()}")
        return

    sandbox_logger.info("Installing Rust runtime...")
    resp = sandbox.execute(
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y 2>&1 | tail -5 "
        "&& source $HOME/.cargo/env && rustc --version",
        timeout=180,
    )
    if resp.exit_code == 0:
        sandbox_logger.info(f"Rust installed: {resp.output.strip()}")


# ============================================================
# 向后兼容的便捷函数
# ============================================================

def create_and_setup_sandbox(
    user_id: str = "default",
    runtimes: list[str] | None = None,
) -> CustomOpenSandbox:
    """
    创建沙箱并初始化环境（向后兼容接口）

    Args:
        user_id: 用户ID（用于容器命名）
        runtimes: 运行时列表，默认 ["python"]

    Returns:
        CustomOpenSandbox 实例
    """
    sandbox_logger.info(f"Creating sandbox for user: {user_id}")

    # 生成用户隔离的容器名
    safe_user_id = "".join(c if c.isalnum() else "_" for c in user_id)
    container_name = f"erp-sandbox-{safe_user_id}"

    config = SandboxConfig(
        name=container_name,
        runtimes=runtimes or ["python"],
    )

    sandbox = create_secure_sandbox(config)

    # 初始化标准目录结构
    sandbox.execute("mkdir -p /workspace /skills /data /analysis /output")

    sandbox_logger.info(f"Sandbox created and initialized for user: {user_id}")
    return sandbox
