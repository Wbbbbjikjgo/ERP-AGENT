"""
Docker 沙箱后端
继承 deepagents BaseSandbox，通过 Docker SDK 在隔离容器中执行命令和操作文件。
容器名: erp-sandbox（由用户手动 docker run 启动）.
"""
import docker
from typing import Optional

from deepagents.backends.sandbox import (
    BaseSandbox, ExecuteResponse,
    FileDownloadResponse, FileUploadResponse,
)
from deepagents.backends import DEFAULT_EXECUTE_TIMEOUT
from ..log_utils import sandbox_logger
from ..config import SANDBOX_WORK_DIR

    
class CustomOpenSandbox(BaseSandbox):
    """
    Docker 容器沙箱后端

    通过 Docker SDK exec_run 在已运行的容器中执行命令。
    继承 BaseSandbox 后，ls/read/write/edit/glob/grep 等文件操作
    自动委托给 execute()（即 docker exec）。

    使用方式：
        backend = DockerSandboxBackend(container_name="erp-sandbox")
        result = backend.execute("python -c 'print(1+1)'")
    """

    def __init__(
        self,
        container_name: str = "erp-sandbox",
        work_dir: str = SANDBOX_WORK_DIR,
        timeout: int = DEFAULT_EXECUTE_TIMEOUT,
    ):
        self._container_name = container_name
        self._work_dir = work_dir
        self._default_timeout = timeout
        self._client: Optional[docker.DockerClient] = None
        self._container = None
        self._connect()

    def _connect(self):
        """连接到 Docker 容器"""
        try:
            self._client = docker.from_env()
            self._container = self._client.containers.get(self._container_name)
            if self._container.status != "running":
                raise RuntimeError(
                    f"Container '{self._container_name}' is not running "
                    f"(status: {self._container.status})"
                )
            # 确保工作目录存在
            self._container.exec_run(f"mkdir -p {self._work_dir}")
            sandbox_logger.info(
                f"Docker sandbox connected: {self._container_name} "
                f"({self._container.id[:12]})"
            )
        except docker.errors.NotFound:
            raise RuntimeError(
                f"Docker container '{self._container_name}' not found. "
                f"Please start it with:\n"
                f"  docker run -d --name {self._container_name} "
                f"-w {self._work_dir} python:3.11-slim sleep infinity"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Docker sandbox: {e}")

    @property
    def id(self) -> str:
        """沙箱唯一标识"""
        if self._container:
            return self._container.id[:12]
        return "disconnected"

    @property
    def container_id(self) -> str:
        """容器完整ID（供 SandboxManager 使用）"""
        if self._container:
            return self._container.id
        return ""

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        """
        在 Docker 容器中执行 shell 命令

        Args:
            command: shell 命令字符串
            timeout: 超时秒数（None 使用默认值）

        Returns:
            ExecuteResponse(output, exit_code, truncated)
        """
        if self._container is None:
            return ExecuteResponse(
                output="[沙箱未连接] 请先启动 Docker 容器",
                exit_code=-1,
            )

        effective_timeout = timeout or self._default_timeout

        try:
            # 在工作目录下执行命令
            exec_result = self._container.exec_run(
                cmd=["bash", "-c", f"cd {self._work_dir} && {command}"],
                demux=True,  # 分离 stdout/stderr
                workdir=self._work_dir,
            )

            exit_code = exec_result.exit_code
            stdout, stderr = exec_result.output

            # 合并输出
            output_parts = []
            if stdout:
                output_parts.append(
                    stdout.decode("utf-8", errors="replace")
                )
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(stderr_text)

            output = "\n".join(output_parts) if output_parts else ""

            # 截断过长输出
            truncated = False
            max_bytes = 100_000
            if len(output) > max_bytes:
                output = output[:max_bytes] + "\n... [output truncated]"
                truncated = True

            return ExecuteResponse(
                output=output,
                exit_code=exit_code,
                truncated=truncated,
            )

        except Exception as e:
            sandbox_logger.error(f"Docker exec failed: {e}")
            return ExecuteResponse(
                output=f"[执行错误] {str(e)}",
                exit_code=-1,
            )

    def ping(self) -> bool:
        """健康检查：容器是否仍在运行"""
        try:
            if self._container is None:
                return False
            self._container.reload()
            return self._container.status == "running"
        except Exception:
            return False

    def destroy(self):
        """断开连接（不销毁容器，容器由用户管理）"""
        self._container = None
        if self._client:
            self._client.close()
            self._client = None
        sandbox_logger.info("Docker sandbox disconnected")

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从容器中下载文件"""
        results = []
        for path in paths:
            try:
                # 使用 docker cp 的替代方案：通过 exec + base64 读取
                resp = self.execute(f"base64 '{path}'")
                if resp.exit_code == 0 and resp.output.strip():
                    import base64
                    content = base64.b64decode(resp.output.strip())
                    results.append(FileDownloadResponse(path=path, content=content, error=None))
                else:
                    results.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
            except Exception as e:
                results.append(FileDownloadResponse(path=path, content=None, error=str(e)))
        return results

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传文件到容器"""
        import base64
        import io
        import tarfile
        results = []
        for path, content in files:
            try:
                # 使用 tar 流通过 put_archive 写入
                dir_name = "/".join(path.rstrip("/").split("/")[:-1]) or "/"
                file_name = path.split("/")[-1]

                tar_stream = io.BytesIO()
                with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                    info = tarfile.TarInfo(name=file_name)
                    info.size = len(content)
                    tar.addfile(info, io.BytesIO(content))
                tar_stream.seek(0)

                self._container.put_archive(dir_name, tar_stream.read())
                results.append(FileUploadResponse(path=path, error=None))
            except Exception as e:
                results.append(FileUploadResponse(path=path, error=str(e)))
        return results
