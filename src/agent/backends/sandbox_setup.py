"""
沙箱创建 + Python 环境初始化
"""
from .custom_opensandbox import CustomOpenSandbox
from ..log_utils import sandbox_logger


def create_and_setup_sandbox(user_id: str = "default") -> CustomOpenSandbox:
    """创建沙箱并初始化环境"""
    sandbox_logger.info(f"Creating sandbox for user: {user_id}")
    sandbox = CustomOpenSandbox()

    # 初始化目录结构
    sandbox.execute("mkdir -p /workspace /skills /data /analysis")

    # 安装常用 Python 包（生产环境在 Docker 镜像中预装）
    # sandbox.execute("pip install matplotlib pandas numpy -q")

    sandbox_logger.info(f"Sandbox created and initialized for user: {user_id}")
    return sandbox
