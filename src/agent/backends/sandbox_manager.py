"""
沙箱生命周期管理（Harness 五态模型）

五态流转：
┌─────────┐    认领     ┌─────────┐    持久化    ┌────────────┐
│  预热池  │ ──────────→ │  已认领  │ ──────────→ │ MongoDB缓存 │
│ (WARM)  │             │ (CLAIMED)│             │  (CACHED)  │
└─────────┘             └─────────┘             └────────────┘
     ↑                       │
     │ 补充预热               │ 故障/超时
     │                       ↓
┌─────────┐             ┌─────────┐
│  新建    │ ←────────── │  销毁    │
│ (CREATE)│   预热池空    │(DESTROY)│
└─────────┘             └─────────┘

设计要点：
- 预热池保持 N 个空闲容器，认领时 < 100ms
- MongoDB 持久化 user→container 映射，服务重启不丢失
- 健康检查 + 自动重建故障容器
- 超时回收闲置沙箱（默认 30 分钟）
"""
import time
import threading
from typing import Dict, Optional
from datetime import datetime, timedelta

from .custom_opensandbox import CustomOpenSandbox
from .sandbox_setup import create_and_setup_sandbox, SandboxConfig, create_secure_sandbox
from ..log_utils import sandbox_logger


# ============================================================
# 沙箱状态枚举
# ============================================================

class SandboxState:
    WARM = "warm"           # 预热池中的空闲容器
    CLAIMED = "claimed"     # 已分配给用户
    CACHED = "cached"       # 已持久化到 MongoDB
    CREATING = "creating"   # 正在创建中
    DESTROYED = "destroyed" # 已销毁


# ============================================================
# 沙箱元数据
# ============================================================

class SandboxEntry:
    """沙箱条目（跟踪容器的完整生命周期）"""

    def __init__(
        self,
        sandbox: CustomOpenSandbox,
        user_id: str = "",
        state: str = SandboxState.WARM,
    ):
        self.sandbox = sandbox
        self.user_id = user_id
        self.state = state
        self.created_at = datetime.now()
        self.claimed_at: Optional[datetime] = None
        self.last_active_at = datetime.now()

    def touch(self):
        """更新活跃时间"""
        self.last_active_at = datetime.now()

    @property
    def container_name(self) -> str:
        return self.sandbox.container_name

    @property
    def container_id(self) -> str:
        return self.sandbox.container_id

    def is_healthy(self) -> bool:
        """检查容器是否健康"""
        return self.sandbox.ping()

    def to_dict(self) -> dict:
        """序列化为字典（用于 MongoDB 存储）"""
        return {
            "container_name": self.container_name,
            "container_id": self.container_id,
            "user_id": self.user_id,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "last_active_at": self.last_active_at.isoformat(),
        }


# ============================================================
# 沙箱生命周期管理器
# ============================================================

class SandboxManager:
    """
    沙箱生命周期管理器（Harness 五态模型）

    核心职责：
    1. 预热池管理：保持 N 个空闲容器随时可用
    2. 认领机制：用户请求时从预热池快速分配
    3. MongoDB 缓存：持久化 user→container 映射
    4. 自动新建：预热池空时按需创建
    5. 超时回收 + 故障自动重建
    """

    _instance: Optional['SandboxManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        warm_pool_size: int = 2,
        idle_timeout_minutes: int = 30,
    ):
        if self._initialized:
            return
        self._initialized = True

        # --- 核心状态 ---
        self._entries: Dict[str, SandboxEntry] = {}   # container_name → entry
        self._user_map: Dict[str, str] = {}           # user_id → container_name

        # --- 配置 ---
        self._warm_pool_size = warm_pool_size
        self._idle_timeout = timedelta(minutes=idle_timeout_minutes)
        self._lock = threading.Lock()

        sandbox_logger.info(
            f"SandboxManager initialized (warm_pool={warm_pool_size}, "
            f"idle_timeout={idle_timeout_minutes}min)"
        )

    # ============================================================
    # 预热池管理
    # ============================================================

    def ensure_warm_pool(self):
        """确保预热池中有足够的空闲容器"""
        with self._lock:
            warm_count = sum(
                1 for e in self._entries.values()
                if e.state == SandboxState.WARM
            )

            needed = self._warm_pool_size - warm_count
            if needed <= 0:
                return

            sandbox_logger.info(f"Warm pool refill: need {needed} more containers")

        # 在锁外创建容器（避免长时间持有锁）
        for i in range(needed):
            try:
                entry = self._create_warm_container()
                with self._lock:
                    self._entries[entry.container_name] = entry
                sandbox_logger.info(
                    f"Warm pool container created: {entry.container_name}"
                )
            except Exception as e:
                sandbox_logger.error(f"Failed to create warm pool container: {e}")

    def _create_warm_container(self) -> SandboxEntry:
        """创建一个预热容器"""
        # 生成唯一容器名
        ts = int(time.time() * 1000) % 100000
        name = f"erp-sandbox-warm-{ts}"

        config = SandboxConfig(name=name, runtimes=["python"])
        sandbox = create_secure_sandbox(config)
        sandbox.execute("mkdir -p /workspace /skills /data /analysis /output")

        return SandboxEntry(sandbox=sandbox, state=SandboxState.WARM)

    # ============================================================
    # 认领机制（用户请求沙箱）
    # ============================================================

    def get_sandbox(self, user_id: str) -> CustomOpenSandbox:
        """
        获取用户的沙箱实例

        优先级：
        1. 已有且健康 → 直接返回
        2. 预热池有空闲 → 认领
        3. MongoDB 有缓存且健康 → 恢复
        4. 新建容器
        """
        with self._lock:
            # 1. 检查用户是否已有沙箱
            container_name = self._user_map.get(user_id)
            if container_name and container_name in self._entries:
                entry = self._entries[container_name]
                if entry.is_healthy():
                    entry.touch()
                    sandbox_logger.debug(f"Returning existing sandbox for {user_id}")
                    return entry.sandbox
                else:
                    # 容器故障，清理并重建
                    sandbox_logger.warning(
                        f"Sandbox unhealthy for {user_id}, will rebuild"
                    )
                    self._remove_entry(entry)

        # 2. 尝试从预热池认领
        claimed = self._claim_from_warm_pool(user_id)
        if claimed:
            return claimed

        # 3. 尝试从 MongoDB 恢复
        restored = self._restore_from_mongodb(user_id)
        if restored:
            return restored

        # 4. 新建容器
        sandbox_logger.info(f"No warm/cached sandbox for {user_id}, creating new")
        return self._create_for_user(user_id)

    def _claim_from_warm_pool(self, user_id: str) -> Optional[CustomOpenSandbox]:
        """从预热池中认领一个空闲容器"""
        with self._lock:
            for entry in self._entries.values():
                if entry.state == SandboxState.WARM and entry.is_healthy():
                    # 认领！
                    entry.user_id = user_id
                    entry.state = SandboxState.CLAIMED
                    entry.claimed_at = datetime.now()
                    entry.touch()
                    self._user_map[user_id] = entry.container_name

                    sandbox_logger.info(
                        f"Claimed warm sandbox {entry.container_name} for {user_id}"
                    )

                    # 异步持久化到 MongoDB
                    self._persist_to_mongodb(entry)

                    # 补充预热池
                    threading.Thread(
                        target=self.ensure_warm_pool,
                        daemon=True,
                    ).start()

                    return entry.sandbox

        return None

    def _create_for_user(self, user_id: str) -> CustomOpenSandbox:
        """为用户创建新容器"""
        safe_user_id = "".join(c if c.isalnum() else "_" for c in user_id)
        name = f"erp-sandbox-{safe_user_id}-{int(time.time()) % 10000}"

        config = SandboxConfig(name=name, runtimes=["python"])
        sandbox = create_secure_sandbox(config)
        sandbox.execute("mkdir -p /workspace /skills /data /analysis /output")

        entry = SandboxEntry(
            sandbox=sandbox,
            user_id=user_id,
            state=SandboxState.CLAIMED,
        )
        entry.claimed_at = datetime.now()

        with self._lock:
            self._entries[name] = entry
            self._user_map[user_id] = name

        self._persist_to_mongodb(entry)
        sandbox_logger.info(f"New sandbox created for {user_id}: {name}")
        return sandbox

    # ============================================================
    # MongoDB 缓存（持久化 user→container 映射）
    # ============================================================

    def _persist_to_mongodb(self, entry: SandboxEntry):
        """将沙箱映射持久化到 MongoDB"""
        try:
            from pymongo import MongoClient
            import os
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            db_name = os.getenv("MONGODB_DB_NAME", "erp_agent")

            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            db = client[db_name]

            db.sandbox_cache.update_one(
                {"user_id": entry.user_id},
                {"$set": entry.to_dict()},
                upsert=True,
            )
            entry.state = SandboxState.CACHED
            client.close()
            sandbox_logger.debug(f"Persisted sandbox cache for {entry.user_id}")
        except Exception as e:
            sandbox_logger.warning(f"Failed to persist sandbox cache: {e}")

    def _restore_from_mongodb(self, user_id: str) -> Optional[CustomOpenSandbox]:
        """从 MongoDB 恢复沙箱映射"""
        try:
            from pymongo import MongoClient
            import os
            import docker
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            db_name = os.getenv("MONGODB_DB_NAME", "erp_agent")

            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            db = client[db_name]

            doc = db.sandbox_cache.find_one({"user_id": user_id})
            client.close()

            if not doc:
                return None

            container_name = doc.get("container_name", "")
            sandbox_logger.info(
                f"Found cached sandbox mapping: {user_id} -> {container_name}"
            )

            # 尝试连接已有容器
            docker_client = docker.from_env()
            try:
                container = docker_client.containers.get(container_name)
                if container.status == "running":
                    sandbox = CustomOpenSandbox(container_name=container_name)
                    entry = SandboxEntry(
                        sandbox=sandbox,
                        user_id=user_id,
                        state=SandboxState.CACHED,
                    )
                    entry.claimed_at = datetime.now()

                    with self._lock:
                        self._entries[container_name] = entry
                        self._user_map[user_id] = container_name

                    sandbox_logger.info(
                        f"Restored sandbox from MongoDB cache: {container_name}"
                    )
                    return sandbox
                else:
                    # 容器已停止，清理缓存
                    sandbox_logger.info(
                        f"Cached container not running ({container.status}), cleaning cache"
                    )
                    self._cleanup_mongodb_cache(user_id)
            except docker.errors.NotFound:
                sandbox_logger.info(
                    f"Cached container not found, cleaning cache"
                )
                self._cleanup_mongodb_cache(user_id)
            finally:
                docker_client.close()

        except Exception as e:
            sandbox_logger.warning(f"Failed to restore from MongoDB cache: {e}")

        return None

    def _cleanup_mongodb_cache(self, user_id: str):
        """清理 MongoDB 中的无效缓存"""
        try:
            from pymongo import MongoClient
            import os
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            db_name = os.getenv("MONGODB_DB_NAME", "erp_agent")

            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            db = client[db_name]
            db.sandbox_cache.delete_one({"user_id": user_id})
            client.close()
        except Exception as e:
            sandbox_logger.warning(f"Failed to cleanup MongoDB cache: {e}")

    # ============================================================
    # 重建 / 销毁
    # ============================================================

    def rebuild(self, user_id: str = "default_user") -> CustomOpenSandbox:
        """重建用户沙箱（故障恢复）"""
        with self._lock:
            container_name = self._user_map.get(user_id)
            if container_name and container_name in self._entries:
                entry = self._entries[container_name]
                self._remove_entry(entry)

        return self._create_for_user(user_id)

    def destroy_user_sandbox(self, user_id: str):
        """销毁用户沙箱"""
        with self._lock:
            container_name = self._user_map.pop(user_id, None)
            if container_name and container_name in self._entries:
                entry = self._entries[container_name]
                self._remove_entry(entry)
                self._cleanup_mongodb_cache(user_id)
                sandbox_logger.info(f"Sandbox destroyed for user: {user_id}")

    def destroy_all(self):
        """销毁所有沙箱"""
        with self._lock:
            for entry in list(self._entries.values()):
                try:
                    entry.sandbox.destroy_container()
                except Exception:
                    pass
            self._entries.clear()
            self._user_map.clear()
        sandbox_logger.info("All sandboxes destroyed")

    # ============================================================
    # 超时回收
    # ============================================================

    def cleanup_idle_sandboxes(self):
        """回收超时的空闲沙箱"""
        now = datetime.now()
        with self._lock:
            for entry in list(self._entries.values()):
                if entry.state in (SandboxState.CLAIMED, SandboxState.CACHED):
                    idle_time = now - entry.last_active_at
                    if idle_time > self._idle_timeout:
                        sandbox_logger.info(
                            f"Reclaiming idle sandbox: {entry.container_name} "
                            f"(idle {idle_time.total_seconds()/60:.0f}min)"
                        )
                        user_id = entry.user_id
                        self._remove_entry(entry)
                        if user_id:
                            self._user_map.pop(user_id, None)
                            self._cleanup_mongodb_cache(user_id)

    # ============================================================
    # 健康检查
    # ============================================================

    def get_active_container(self, user_id: str = "default_user") -> Optional[str]:
        """获取用户当前活跃的容器ID（供健康检查中间件使用）"""
        with self._lock:
            container_name = self._user_map.get(user_id)
            if container_name and container_name in self._entries:
                entry = self._entries[container_name]
                if entry.is_healthy():
                    return entry.container_id
        return None

    def health_check_all(self):
        """检查所有沙箱健康状态"""
        with self._lock:
            unhealthy = []
            for name, entry in self._entries.items():
                if not entry.is_healthy():
                    unhealthy.append(entry)

        # 在锁外重建故障容器
        for entry in unhealthy:
            sandbox_logger.warning(
                f"Unhealthy sandbox detected: {entry.container_name} "
                f"(user={entry.user_id})"
            )
            if entry.user_id:
                self.rebuild(entry.user_id)

    # ============================================================
    # 内部工具
    # ============================================================

    def _remove_entry(self, entry: SandboxEntry):
        """移除并销毁一个条目（必须在锁内调用）"""
        try:
            entry.sandbox.destroy_container()
        except Exception:
            pass
        entry.state = SandboxState.DESTROYED
        self._entries.pop(entry.container_name, None)
        if entry.user_id:
            self._user_map.pop(entry.user_id, None)


# ============================================================
# 全局单例
# ============================================================

sandbox_manager = SandboxManager()
