"""
沙箱代理层（热替换，18个方法显式委托）
SandboxBackendProxy - 稳定句柄层，支持运行时热替换底层沙箱实例.

设计原则：
- 对外提供稳定接口，内部可动态切换沙箱实例
- 所有方法直接委托给 CustomOpenSandbox 的真实实现
- replace_backend() 支持热替换（沙箱故障恢复时无缝切换）
"""
from typing import Optional, List
from .custom_opensandbox import CustomOpenSandbox, ExecuteResponse
from ..log_utils import sandbox_logger


class SandboxBackendProxy:
    """
    沙箱代理器 - 18个方法显式委托 + replace_backend() 热替换
    对外提供稳定接口，内部可动态切换沙箱实例
    """

    def __init__(self, backend: Optional[CustomOpenSandbox] = None):
        self._backend = backend

    def replace_backend(self, new_backend: CustomOpenSandbox):
        """热替换底层沙箱实例（故障恢复 / 切换运行时环境）"""
        old = self._backend
        self._backend = new_backend
        if old:
            old.destroy()
        sandbox_logger.info("Sandbox backend hot-swapped")

    @property
    def backend(self) -> CustomOpenSandbox:
        if self._backend is None:
            raise RuntimeError("No sandbox backend available")
        return self._backend

    # ============================================================
    # 18个显式委托方法 — 全部委托到 CustomOpenSandbox 真实实现
    # ============================================================

    # 1. execute — 执行 shell 命令
    def execute(self, command: str, timeout: int = 30) -> ExecuteResponse:
        return self.backend.execute(command, timeout=timeout)

    # 2. read_file — 读取文件内容
    def read_file(self, path: str) -> str:
        return self.backend.read_file(path)

    # 3. write_file — 写入文件
    def write_file(self, path: str, content: str | bytes) -> str:
        return self.backend.write_file(path, content)

    # 4. list_dir — 列出目录
    def list_dir(self, path: str = ".") -> list[str]:
        return self.backend.list_dir(path)

    # 5. ping — 健康检查
    def ping(self) -> bool:
        if self._backend is None:
            return False
        return self._backend.ping()

    # 6. destroy — 断开连接
    def destroy(self):
        if self._backend:
            self._backend.destroy()

    # 7. edit_file — 编辑文件（文本替换）
    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        return self.backend.edit_file(path, old_text, new_text)

    # 8. glob — 文件模式匹配
    def glob(self, pattern: str, base_path: str = ".") -> list[str]:
        return self.backend.glob(pattern, base_path)

    # 9. grep — 文件内容搜索
    def grep(self, pattern: str, path: str = ".", recursive: bool = True) -> list[str]:
        return self.backend.grep(pattern, path, recursive)

    # 10. mkdir — 创建目录
    def mkdir(self, path: str) -> str:
        return self.backend.mkdir(path)

    # 11. rm — 删除文件/目录
    def rm(self, path: str) -> str:
        return self.backend.rm(path)

    # 12. cp — 复制文件/目录
    def cp(self, src: str, dst: str) -> str:
        return self.backend.cp(src, dst)

    # 13. mv — 移动文件/目录
    def mv(self, src: str, dst: str) -> str:
        return self.backend.mv(src, dst)

    # 14. cat — 读取文件（同 read_file）
    def cat(self, path: str) -> str:
        return self.backend.cat(path)

    # 15. pwd — 获取当前工作目录
    def pwd(self) -> str:
        return self.backend.pwd()

    # 16. env — 获取环境变量
    def env(self) -> str:
        return self.backend.env()

    # 17. pip_install — 安装 Python 包
    def pip_install(self, package: str) -> str:
        return self.backend.pip_install(package)

    # 18. python_exec — 执行 Python 脚本
    def python_exec(self, script: str) -> ExecuteResponse:
        return self.backend.python_exec(script)

    # ============================================================
    # 扩展运行时方法
    # ============================================================

    def go_exec(self, code: str) -> ExecuteResponse:
        """执行 Go 代码"""
        return self.backend.go_exec(code)

    def node_exec(self, code: str) -> ExecuteResponse:
        """执行 Node.js 代码"""
        return self.backend.node_exec(code)

    def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        return self.backend.file_exists(path)

    def download_file_to_host(self, remote_path: str, local_path: str) -> str:
        """从沙箱下载文件到宿主机"""
        return self.backend.download_file_to_host(remote_path, local_path)

    def upload_directory(self, local_dir: str, remote_dir: str) -> str:
        """上传整个目录到沙箱"""
        return self.backend.upload_directory(local_dir, remote_dir)
