"""
Session Management - 会话元数据管理

管理 GDB 调试会话的生命周期：
- 创建、查询、清理
- 幂等性保证（同 PID 不重复 attach）
"""


import json
import os
import shutil
import signal
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

# Session 目录
SESSION_DIR = Path.home() / ".gdb-cli" / "sessions"

# Serializes session creation so concurrent creators cannot race on metadata.
_create_lock = threading.Lock()

# Sessions younger than this are not reaped: creation writes meta.json before
# the GDB PID, so a concurrent creator would otherwise look dead.
SESSION_CREATION_GRACE = 60.0


@dataclass
class SessionMeta:
    """会话元数据"""
    session_id: str                    # UUID
    mode: str                          # "core" | "attach" | "target"
    binary: Optional[str] = None       # 可执行文件路径
    core: Optional[str] = None         # Core dump 路径 (core 模式)
    pid: Optional[int] = None          # 目标进程 PID (attach 模式)
    remote: Optional[str] = None       # host:port for target
    gdb_pid: Optional[int] = None      # GDB 进程 PID
    gdb_start_time: Optional[str] = None  # /proc/<pid>/stat starttime for identity
    sock_path: Optional[str] = None    # Unix Socket 路径
    started_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    heartbeat_timeout: int = 600       # 心跳超时秒数
    safety_level: str = "readonly"     # "readonly" | "readwrite" | "full"

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SessionMeta':
        """从字典创建"""
        return cls(**data)


def create_session(
    mode: str,
    binary: Optional[str] = None,
    core: Optional[str] = None,
    pid: Optional[int] = None,
    remote: Optional[str] = None,
    timeout: int = 600,
    safety_level: str = "readonly"
) -> SessionMeta:
    """
    创建新会话

    Args:
        mode: 模式 ("core" | "attach" | "target")
        binary: 可执行文件路径
        core: Core dump 路径
        pid: 目标进程 PID
        remote: host:port
        timeout: 心跳超时秒数
        safety_level: 安全级别

    Returns:
        SessionMeta 实例
    """
    # 生成 session ID
    session_id = str(uuid.uuid4())[:8]

    # 创建 session 目录
    session_dir = SESSION_DIR / session_id

    # Socket 路径
    sock_path = session_dir / "gdb.sock"

    # 创建元数据
    session = SessionMeta(
        session_id=session_id,
        mode=mode,
        binary=binary,
        core=core,
        pid=pid,
        remote=remote,
        sock_path=str(sock_path),
        heartbeat_timeout=timeout,
        safety_level=safety_level
    )

    with _create_lock:
        session_dir.mkdir(parents=True, exist_ok=True)

        # 写入 meta.json
        _write_meta(session)

    return session


def _write_meta(session: SessionMeta) -> None:
    """写入 meta.json（原子写：先写临时文件再重命名，避免 TOCTOU 竞态。）"""
    session_dir = SESSION_DIR / session.session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    meta_path = session_dir / "meta.json"
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=session_dir, delete=False, suffix=".tmp"
        ) as f:
            temp_path = f.name
            json.dump(session.to_dict(), f, indent=2)
        Path(temp_path).replace(meta_path)
    except Exception:
        # 清理临时文件
        try:
            Path(temp_path).unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        raise


def _read_meta(session_id: str) -> Optional[SessionMeta]:
    """读取 meta.json"""
    meta_path = SESSION_DIR / session_id / "meta.json"
    if not meta_path.exists():
        return None

    try:
        with open(meta_path) as f:
            data = json.load(f)
        return SessionMeta.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def get_session(session_id: str) -> Optional[SessionMeta]:
    """
    获取会话

    Args:
        session_id: 会话 ID

    Returns:
        SessionMeta 或 None
    """
    return _read_meta(session_id)


def list_sessions(alive_only: bool = True) -> List[SessionMeta]:
    """
    列出所有会话

    Args:
        alive_only: 是否只返回存活的会话

    Returns:
        SessionMeta 列表
    """
    sessions = []

    if not SESSION_DIR.exists():
        return sessions

    for session_dir in SESSION_DIR.iterdir():
        if not session_dir.is_dir():
            continue

        session_id = session_dir.name
        meta = _read_meta(session_id)
        if meta is None:
            continue

        if alive_only:
            # 检查 GDB 进程是否存活
            if not _is_session_alive(meta):
                continue

        sessions.append(meta)

    # 按最后活跃时间排序
    sessions.sort(key=lambda s: s.last_active, reverse=True)

    return sessions


def _is_session_alive(session: SessionMeta) -> bool:
    """检查会话是否存活（包含 PID 复用检测）"""
    if session.gdb_pid is None:
        return False

    # 检查进程是否存在
    try:
        os.kill(session.gdb_pid, 0)
    except OSError:
        return False

    # 交叉验证进程名称，防止 PID 复用
    try:
        import psutil
        proc = psutil.Process(session.gdb_pid)
        return "gdb" in proc.name().lower()
    except ImportError:
        pass  # psutil 不可用，回退到仅检查 PID

    return True


def _read_proc_starttime(pid: int) -> Optional[str]:
    """Return /proc/<pid>/stat field 22 (starttime) as a string, or None.

    The comm field (field 2) may contain spaces and parentheses, so parsing
    resumes after the last ')'.
    """
    try:
        with open(f"/proc/{pid}/stat") as f:
            data = f.read()
    except OSError:
        return None

    rparen = data.rfind(")")
    if rparen == -1:
        return None

    # Fields after ')' start at field 3 (state); starttime is field 22.
    fields = data[rparen + 1:].split()
    try:
        return fields[19]
    except IndexError:
        return None


def _read_proc_comm(pid: int) -> Optional[str]:
    """Return /proc/<pid>/comm (the executable name) or None."""
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip()
    except OSError:
        return None


def _process_identity_matches(meta: SessionMeta) -> bool:
    """Check whether meta.gdb_pid still belongs to the GDB we launched.

    Sessions created by older versions have no start time; for those fall
    back to the weak executable-name check.
    """
    if meta.gdb_pid is None:
        return False

    if meta.gdb_start_time is not None:
        current = _read_proc_starttime(meta.gdb_pid)
        return current is not None and current == meta.gdb_start_time

    comm = _read_proc_comm(meta.gdb_pid)
    return comm is not None and "gdb" in comm.lower()


def cleanup_session(session_id: str) -> bool:
    """
    清理会话

    Args:
        session_id: 会话 ID

    Returns:
        是否成功清理
    """
    session_dir = SESSION_DIR / session_id
    if not session_dir.exists():
        return False

    # 读取元数据，尝试杀死 GDB 进程
    meta = _read_meta(session_id)
    if meta and meta.gdb_pid:
        # Only signal the process when it is still the one we launched. A
        # recycled PID (or a process that already exited) must never be killed.
        if _process_identity_matches(meta):
            try:
                os.kill(meta.gdb_pid, signal.SIGTERM)
                # 等待进程退出，否则发送 SIGKILL
                deadline = time.time() + 3.0
                while time.time() < deadline:
                    try:
                        os.kill(meta.gdb_pid, 0)
                        time.sleep(0.1)
                    except OSError:
                        break  # 进程已退出
                else:
                    # 超时仍未退出，强制 SIGKILL
                    try:
                        os.kill(meta.gdb_pid, signal.SIGKILL)
                    except OSError:
                        pass
            except OSError:
                pass
        # else: the PID is gone or reused by an unrelated process; do not
        # signal it. The metadata cleanup below still succeeds.

    # 删除目录
    try:
        shutil.rmtree(session_dir)
        return True
    except Exception:
        return False


def cleanup_dead_sessions() -> int:
    """
    清理所有僵尸会话

    Returns:
        清理的会话数量
    """
    cleaned = 0

    if not SESSION_DIR.exists():
        return cleaned

    for session_dir in SESSION_DIR.iterdir():
        if not session_dir.is_dir():
            continue

        session_id = session_dir.name
        meta = _read_meta(session_id)
        if meta is None:
            # 无效的 session 目录，删除
            try:
                shutil.rmtree(session_dir)
                cleaned += 1
            except Exception:
                pass
            continue

        # A session that was just created may not have its GDB PID written
        # yet; leave it alone during the creation grace period.
        if time.time() - meta.started_at < SESSION_CREATION_GRACE:
            continue

        # 检查是否存活
        if not _is_session_alive(meta):
            cleanup_session(session_id)
            cleaned += 1

    return cleaned


def find_session_by_pid(pid: int) -> Optional[SessionMeta]:
    """
    查找 attach 到指定 PID 的会话

    用于幂等性保证：同 PID 不重复 attach

    Args:
        pid: 目标进程 PID

    Returns:
        已存在的 SessionMeta 或 None
    """
    sessions = list_sessions(alive_only=True)
    for session in sessions:
        if session.mode == "attach" and session.pid == pid:
            return session
    return None


def find_session_by_core(core: str) -> Optional[SessionMeta]:
    """
    查找加载指定 core 文件的会话

    Args:
        core: Core dump 文件路径

    Returns:
        已存在的 SessionMeta 或 None
    """
    core_path = Path(core).resolve()
    sessions = list_sessions(alive_only=True)
    for session in sessions:
        if session.mode == "core" and session.core:
            if Path(session.core).resolve() == core_path:
                return session
    return None


def find_session_by_remote(remote: str) -> Optional[SessionMeta]:
    """
    Args:
        remote: host:port

    Returns:
        已存在的 SessionMeta 或 None
    """
    sessions = list_sessions(alive_only=True)
    for session in sessions:
        if session.mode == "target" and session.remote == remote:
            return session
    return None


def update_session_activity(session_id: str) -> None:
    """更新会话最后活跃时间"""
    meta = _read_meta(session_id)
    if meta:
        meta.last_active = time.time()
        _write_meta(meta)
