"""
沙箱代理层（热替换，18个方法显式委托）
SandboxBackendProxy - 稳定句柄层，支持运行时热替换底层沙箱实例
"""
from typing import Optional
from .custom_opensandbox import CustomOpenSandbox
from ..log_utils import sandbox_logger


class SandboxBackendProxy:
    """
    沙箱代理器 - 18个方法显式委托 + replace_backend() 热替换
    对外提供稳定接口，内部可动态切换沙箱实例
    """

    def __init__(self, backend: Optional[CustomOpenSandbox] = None):
        self._backend = backend

    def replace_backend(self, new_backend: CustomOpenSandbox):
        """热替换底层沙箱实例"""
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

    # === 18个显式委托方法 ===

    def execute(self, command: str, timeout: int = 30) -> dict:
        return self.backend.execute(command, timeout)

    def read_file(self, path: str) -> str:
        return self.backend.read_file(path)

    def write_file(self, path: str, content: str) -> str:
        return self.backend.write_file(path, content)

    def list_dir(self, path: str = ".") -> list:
        return self.backend.list_dir(path)

    def ping(self) -> bool:
        if self._backend is None:
            return False
        return self._backend.ping()

    def destroy(self):
        if self._backend:
            self._backend.destroy()

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        """编辑文件：替换文本"""
        content = self.backend.read_file(path)
        if old_text in content:
            content = content.replace(old_text, new_text, 1)
            return self.backend.write_file(path, content)
        return f"Text not found in {path}"

    def glob(self, pattern: str) -> list:
        """文件模式匹配"""
        import fnmatch
        all_files = self.backend.list_dir(".")
        return [f for f in all_files if fnmatch.fnmatch(f, pattern)]

    def grep(self, pattern: str, path: str = ".") -> list:
        """在文件中搜索文本"""
        import re
        results = []
        content = self.backend.read_file(path)
        for i, line in enumerate(content.split("\n"), 1):
            if re.search(pattern, line):
                results.append(f"{i}: {line}")
        return results

    def mkdir(self, path: str) -> str:
        return self.backend.execute(f"mkdir -p {path}")["stdout"]

    def rm(self, path: str) -> str:
        return self.backend.execute(f"rm -rf {path}")["stdout"]

    def cp(self, src: str, dst: str) -> str:
        return self.backend.execute(f"cp -r {src} {dst}")["stdout"]

    def mv(self, src: str, dst: str) -> str:
        return self.backend.execute(f"mv {src} {dst}")["stdout"]

    def cat(self, path: str) -> str:
        return self.backend.read_file(path)

    def pwd(self) -> str:
        return self.backend.execute("pwd")["stdout"].strip()

    def env(self) -> str:
        return self.backend.execute("env")["stdout"]

    def pip_install(self, package: str) -> str:
        return self.backend.execute(f"pip install {package} -q")["stdout"]

    def python_exec(self, script: str) -> dict:
        """执行 Python 脚本"""
        self.backend.write_file("/tmp/_script.py", script)
        return self.backend.execute("python /tmp/_script.py")
