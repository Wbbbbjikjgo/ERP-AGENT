"""
环境变量加载工具
从项目根目录 .env 文件加载环境变量到 os.environ
"""
import os
from pathlib import Path
from dotenv import load_dotenv


def load_env():
    """加载项目根目录的 .env 文件"""
    # 项目根目录：src/agent/../../.env
    project_root = Path(__file__).parent.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
    else:
        print(f"⚠️ .env file not found at {env_file}")


def get_env(key: str, default: str = None) -> str:
    """获取环境变量"""
    return os.getenv(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """获取整数环境变量"""
    return int(os.getenv(key, str(default)))


# 模块加载时自动加载 .env
load_env()
#加载进去之后可以直接通过 os.getenv(key, default) 获取 key是键  default是默认值
