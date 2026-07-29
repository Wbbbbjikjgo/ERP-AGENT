"""
沙箱全局持有器

让所有工具（document_generator / chart_generator 等）
能够访问当前活跃的沙箱实例，确保文件生成在沙箱中执行。

使用方式：
    from ..backends.sandbox_holder import get_sandbox, set_sandbox
    sandbox = get_sandbox()
    if sandbox:
        sandbox.write_file("/workspace/output/report.md", content)
"""
from typing import Optional

# 全局沙箱实例（由 main_agent.py 在创建 Agent 时设置）
_active_sandbox = None


def set_sandbox(sandbox):
    """设置当前活跃的沙箱实例（main_agent.py 调用）"""
    global _active_sandbox
    _active_sandbox = sandbox


def get_sandbox():
    """获取当前活跃的沙箱实例（工具调用）"""
    return _active_sandbox


def has_sandbox() -> bool:
    """检查沙箱是否可用"""
    if _active_sandbox is None:
        return False
    try:
        return _active_sandbox.ping()
    except Exception:
        return False
