"""
沙箱文件下载工具
从沙箱/工作目录下载文件到宿主机 src/download/ 目录
"""
import os
import shutil
from pathlib import Path
from langchain_core.tools import tool

from ..log_utils import agent_logger

DOWNLOAD_DIR = Path(__file__).parent.parent.parent / "download"


@tool
def download_sandbox_file(remote_path: str) -> str:
    """将文件从工作目录复制到下载目录，供用户访问。

    Args:
        remote_path: 源文件路径（沙箱内或本地工作目录中的路径）

    Returns:
        下载后的本地文件路径
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    source = Path(remote_path)
    if not source.exists():
        return f"文件不存在: {remote_path}"

    if source.is_dir():
        return f"路径是目录而非文件: {remote_path}"

    # 复制到下载目录
    target = DOWNLOAD_DIR / source.name
    try:
        shutil.copy2(source, target)
        agent_logger.info(f"File downloaded: {source} -> {target}")
        return f"文件已保存到: {target}"
    except Exception as e:
        return f"文件复制失败: {str(e)}"
