"""
GDB RPC Server - 运行在 GDB Python 解释器内

通过 source 命令加载到 GDB 中，提供 Unix Domain Socket 接口。
使用 gdb.post_event() 确保所有 GDB API 调用在主线程执行。
"""

import io
import json
import os
import queue
import socket
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# GDB Python API - 仅在 GDB 环境中可用
try:
    import gdb
    GDB_AVAILABLE = True
except ImportError:
    GDB_AVAILABLE = False
    gdb = None  # type: ignore


# 默认配置
DEFAULT_SOCKET_TIMEOUT = 5.0  # 单次 socket 操作超时
DEFAULT_COMMAND_TIMEOUT = 30.0  # 命令执行超时
DEFAULT_REQUEST_DEADLINE = 30.0  # 单个请求从开始接收到完整读取的最长耗时
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB 最大请求


class GDBRPCServer:
    """
    GDB 内嵌 Python RPC Server

    架构:
    - 后台线程: 负责 socket accept/recv/send (I/O only)
    - GDB 主线程: 通过 gdb.post_event() 执行所有 GDB API 调用
    - 结果通过 Queue 在两个线程间传递
    """

    def __init__(
        self,
        sock_path: str,
        session_meta: dict,
        heartbeat_timeout: int = 600,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT
    ):
        """
        初始化 RPC Server

        Args:
            sock_path: Unix Domain Socket 路径
            session_meta: 会话元数据 (mode, binary, core, pid, etc.)
            heartbeat_timeout: 心跳超时秒数，默认 600s (10min)
            command_timeout: 单个命令执行超时秒数
        """
        if not GDB_AVAILABLE:
            raise RuntimeError("GDBRPCServer must run inside GDB Python interpreter")

        self.sock_path = Path(sock_path)
        self.session_meta = session_meta
        self.heartbeat_timeout = heartbeat_timeout
        self.command_timeout = command_timeout

        self.running = False
        self.server_sock: Optional[socket.socket] = None
        self.accept_thread: Optional[threading.Thread] = None
        self.last_active = time.time()
        self.heartbeat_timer: Optional[threading.Timer] = None
        self._heartbeat_generation = 0
        self._heartbeat_lock = threading.Lock()
        self._state = "loading"
        self._error_reason: Optional[str] = None
        self._loading_start = time.time()
        self.LOADING_TIMEOUT = 60.0
        self._loading_timer: Optional[threading.Timer] = None
        self._stop_event = threading.Event()

        # Per-request bookkeeping: ids are monotonically increasing and ids of
        # requests that already timed out are tracked so their late results can
        # be dropped with a log message instead of silently disappearing.
        self._request_counter = 0
        self._abandoned: set = set()
        self._abandoned_lock = threading.Lock()

        # 命令处理器注册表
        self._handlers: Dict[str, Callable] = {}
        self._register_builtin_handlers()

    @property
    def _stop_requested(self) -> bool:
        """Whether a graceful stop has been dispatched.

        Backed by an Event so the accept thread reliably observes the flag set
        by a per-connection thread.
        """
        return self._stop_event.is_set()

    @_stop_requested.setter
    def _stop_requested(self, value: bool) -> None:
        if value:
            self._stop_event.set()
        else:
            self._stop_event.clear()

    def _register_builtin_handlers(self) -> None:
        """注册内置命令处理器"""
        # 动态加载 handlers 模块（避免相对导入问题）
        # NOTE: 不能依赖 __file__ —— GDB 的 source 只在执行脚本期间提供它，
        # 之后调用本函数时全局命名空间里已经没有 __file__ 了。
        import importlib.util
        server_dir = os.environ.get("GDB_CLI_SERVER_DIR")
        if not server_dir:
            module_file = globals().get("__file__")
            if not module_file:
                raise RuntimeError(
                    "Cannot locate gdb_server directory: "
                    "GDB_CLI_SERVER_DIR is not set and __file__ is unavailable"
                )
            server_dir = str(Path(module_file).resolve().parent)
        handlers_path = Path(server_dir) / "handlers.py"
        spec = importlib.util.spec_from_file_location("handlers", handlers_path)
        if spec is None or spec.loader is None:
            raise ImportError(
                f"Cannot load handlers from {handlers_path}: "
                "file not found or invalid"
            )
        handlers = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(handlers)
        except Exception as e:
            raise ImportError(f"Failed to exec handlers module: {e}")

        self._handlers = {
            "eval": handlers.handle_eval,
            "threads": handlers.handle_threads,
            "bt": handlers.handle_backtrace,
            "frame": handlers.handle_frame_select,
            "locals": handlers.handle_locals,
            "exec": handlers.handle_exec,
            "status": handlers.handle_status,
            "eval_element": handlers.handle_eval_element,
            "thread_apply": handlers.handle_thread_apply,
            "args": handlers.handle_args,
            "registers": handlers.handle_registers,
            "memory": handlers.handle_memory,
            "ptype": handlers.handle_ptype,
            "thread_switch": handlers.handle_thread_switch,
            "sharedlibs": handlers.handle_sharedlibs,
            "disasm": handlers.handle_disasm,
            "ping": self._handle_ping,
            "stop": self._handle_stop,
        }

    def _handle_ping(self, **kwargs) -> dict:
        """心跳 ping 处理"""
        return {"pong": True, "time": time.time(), "state": self._state}

    def _handle_stop(self, before_detach: Optional[str] = None, **kwargs) -> dict:
        """Detach from the target and request a graceful GDB shutdown.

        Runs on the GDB main thread.  The accept thread sends the response
        first and only then calls _shutdown_after_stop(), so the client sees
        a clean "stopped" status instead of a connection error.
        """
        result: Dict[str, Any] = {"detached": False, "errors": []}

        # Optional user commands, e.g. "monitor go" to leave the MCU running
        # or "monitor reset" to put the target into a known state.
        if before_detach:
            for line in str(before_detach).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    gdb.execute(line, to_string=True)
                except Exception as e:
                    result["errors"].append(f"{line}: {e}")

        try:
            gdb.execute("detach", to_string=True)
            result["detached"] = True
        except Exception as e:
            message = str(e)
            # Core files and already-detached sessions have no inferior.
            if "No inferior" not in message and "not being run" not in message:
                result["errors"].append(message)

        self._stop_requested = True
        return result

    def _handle_loading_status(self) -> dict:
        """加载阶段的轻量状态查询，不访问 GDB API。"""
        result = {
            "state": self._state,
            "elapsed": time.time() - self._loading_start,
            "session_meta": self.session_meta,
        }
        if self._state == "error" and self._error_reason:
            result["error_reason"] = self._error_reason
        return result

    def set_ready(self) -> None:
        """标记会话已完成初始化，可以处理完整命令集。

        先验证 target/attach/core 初始化是否真的成功：如果当前没有
        inferior，说明连接/attach/加载失败，会话进入 error 状态而不是
        假装 ready（否则 CLI 会报告 started，自动化会误信）。
        """
        if self._state == "loading":
            failure = self._check_inferior_available()
            if failure:
                self._state = "error"
                self._error_reason = failure
                self._cancel_loading_timer()
                return

        self._state = "ready"
        self._cancel_loading_timer()

    def _cancel_loading_timer(self) -> None:
        if self._loading_timer:
            self._loading_timer.cancel()
            self._loading_timer = None

    def _check_inferior_available(self) -> Optional[str]:
        """Verify the session actually has a live inferior.

        Returns None when an inferior exists (or the state cannot be
        determined), or a human-readable failure reason otherwise.
        """
        try:
            inferiors = list(gdb.inferiors())
        except Exception:
            # Very old GDB without the API, or a mock without it configured:
            # assume success.
            return None

        live = [inf for inf in inferiors if getattr(inf, "pid", 0)]
        if inferiors and not live:
            return (
                "GDB session initialized without a live inferior: the "
                "target connection, attach, or file/core load likely failed "
                "(see gdb.log for details)"
            )
        if not inferiors and self.session_meta.get("mode") != "core":
            # No inferior at all is only acceptable for a bare core-file
            # session before the core is opened; for target/attach it means
            # the connection never succeeded.
            return (
                "GDB session initialized with no inferior: the target "
                "connection or attach likely failed (see gdb.log for details)"
            )
        return None

    def start(self) -> None:
        """启动监听线程，注册心跳定时器"""
        if self.running:
            return

        # 确保目录存在
        self.sock_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建 Unix Domain Socket
        self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 清理旧 socket 文件
        if self.sock_path.exists():
            self.sock_path.unlink()

        self.server_sock.bind(str(self.sock_path))
        os.chmod(str(self.sock_path), 0o600)
        self.server_sock.listen(1)
        self.server_sock.settimeout(1.0)  # accept 超时，允许定期检查 running 状态

        self.running = True

        # 启动 accept 线程
        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.accept_thread.start()

        # 启动心跳定时器
        self._start_heartbeat_timer()

        # 启动加载超时定时器
        self._loading_timer = threading.Timer(
            self.LOADING_TIMEOUT, self._loading_timeout
        )
        self._loading_timer.daemon = True
        self._loading_timer.start()

        gdb.write(f"[GDBRPCServer] Listening on {self.sock_path}\n")

    def stop(self) -> None:
        """关闭 socket，清理资源"""
        self.running = False

        # 取消心跳定时器
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None

        # 取消加载超时定时器
        if self._loading_timer:
            self._loading_timer.cancel()
            self._loading_timer = None

        # 关闭 socket
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None

        # 清理 socket 文件
        if self.sock_path.exists():
            try:
                self.sock_path.unlink()
            except Exception:
                pass

        # 等待 accept 线程结束
        if self.accept_thread and self.accept_thread.is_alive():
            self.accept_thread.join(timeout=2.0)

        gdb.write("[GDBRPCServer] Stopped\n")

    def _accept_loop(self) -> None:
        """
        后台线程：accept 连接，然后交给短生命周期线程处理。

        关键约束：此线程绝不直接调用 GDB API。每个连接线程只做 socket
        recv/send；真正的 handler 通过 gdb.post_event() 排队到 GDB 主线程，
        因此多个并发连接可以同时等待，而 ping/status/stop 不会被长命令阻塞。
        """
        while self.running and not self._stop_event.is_set():
            try:
                conn, _ = self.server_sock.accept()  # type: ignore
            except socket.timeout:
                continue  # 定期检查 running 状态
            except OSError:
                break  # socket 已关闭

            worker = threading.Thread(
                target=self._handle_connection, args=(conn,), daemon=True
            )
            worker.start()

        # The stop response has been sent by a worker: shut GDB down from here.
        if self._stop_event.is_set():
            self._shutdown_after_stop()

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle one client connection (I/O only, no direct GDB API calls)."""
        try:
            conn.settimeout(DEFAULT_SOCKET_TIMEOUT)
            data_buffer = io.BytesIO()
            deadline = time.monotonic() + DEFAULT_REQUEST_DEADLINE
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"Request not fully received within "
                        f"{DEFAULT_REQUEST_DEADLINE:.0f}s"
                    )
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data_buffer.write(chunk)
                if data_buffer.tell() > MAX_REQUEST_SIZE:
                    raise ValueError("Request too large")

            if data_buffer.tell() == 0:
                return

            data = data_buffer.getvalue()

            # 解析 JSON 请求
            try:
                request = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError as e:
                self._send_response(
                    conn, {"ok": False, "error": f"Invalid JSON: {e}"}
                )
                return

            # 重置心跳
            self._reset_heartbeat()

            try:
                result = self._dispatch(request)
                response = {"ok": True, "data": result}
            except gdb.MemoryError as e:
                response = {"ok": False, "error": f"Cannot access memory: {e}"}
            except gdb.error as e:  # type: ignore
                response = {"ok": False, "error": f"GDB error: {e}"}
            except Exception as e:
                response = {"ok": False, "error": str(e)}

            self._send_response(conn, response)

        except Exception as e:
            try:
                self._send_response(conn, {"ok": False, "error": str(e)})
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _send_response(self, conn: socket.socket, response: dict) -> None:
        """Serialize and send a response.

        ``allow_nan=False`` keeps the wire protocol strict; the fallback keeps
        a pathological value (NaN or an unserializable object) from tearing
        down the whole server.
        """
        try:
            text = json.dumps(response, allow_nan=False)
        except (TypeError, ValueError):
            text = json.dumps(response, default=str)
        conn.sendall(text.encode("utf-8"))

    def _shutdown_after_stop(self) -> None:
        """Close the socket and quit GDB after a graceful stop.

        Called from the accept thread once the response has been delivered.
        GDB API calls must happen on the main thread, hence post_event().
        """
        self.running = False

        for timer in (self.heartbeat_timer, self._loading_timer):
            if timer:
                timer.cancel()
        self.heartbeat_timer = None
        self._loading_timer = None

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None

        if self.sock_path.exists():
            try:
                self.sock_path.unlink()
            except Exception:
                pass

        gdb.post_event(self._quit_gdb)

    @staticmethod
    def _quit_gdb() -> None:
        """Run on the GDB main thread and exit the process."""
        try:
            gdb.execute("quit")
        except Exception:
            # `quit` may raise as part of GDB's shutdown path; make sure the
            # process still terminates.
            os._exit(0)

    def _dispatch(self, request: dict) -> dict:
        """
        主线程：根据 cmd 分发到具体 handler

        Args:
            request: {"cmd": "...", ...params}

        Returns:
            命令执行结果 (将被包装在 {"ok": True, "data": ...} 中)

        Raises:
            ValueError: 请求非法、会话处于 loading/error 状态，或 handler
                返回顶层 {"error": ...}（旧式错误约定）。
            RuntimeError: handler 抛出异常或执行超时。
        """
        cmd = request.get("cmd")
        if not cmd:
            raise ValueError("Missing 'cmd' in request")

        if self._state == "loading":
            elapsed = time.time() - self._loading_start
            if elapsed > self.LOADING_TIMEOUT:
                self._state = "error"
                self._error_reason = (
                    f"Loading timeout ({elapsed:.0f}s > "
                    f"{self.LOADING_TIMEOUT:.0f}s). "
                    "Binary/core file may not exist or is corrupted."
                )
            else:
                if cmd == "status":
                    return self._handle_loading_status()
                # `stop` must remain available so a stuck load can be aborted.
                if cmd not in ("ping", "status", "stop"):
                    raise ValueError(f"Session is loading ({elapsed:.0f}s elapsed)")

        if self._state == "error":
            if cmd == "status":
                return self._handle_loading_status()
            if cmd not in ("ping", "stop"):
                reason = self._error_reason or "unknown error"
                raise ValueError(
                    f"session failed during initialization: {reason}"
                )

        handler = self._handlers.get(cmd)
        if not handler:
            raise ValueError(f"Unknown command: {cmd}")

        # 提取参数 (排除 'cmd' 字段)
        params = {k: v for k, v in request.items() if k != "cmd"}

        # 注入 session 元数据
        params["_session_meta"] = self.session_meta

        # 注入 server 状态，供 handle_status 报告 loading/error/ready
        params["_server_state"] = self._state

        # 通过 gdb.post_event() 将所有 handler 调用路由到 GDB 主线程
        result_queue: queue.Queue = queue.Queue()

        with self._abandoned_lock:
            self._request_counter += 1
            request_id = self._request_counter

        def run_handler():
            try:
                result = handler(**params)
                if isinstance(result, dict) and "error" in result:
                    # Existing error convention: a TOP-LEVEL "error" key means
                    # the whole command failed. Per-item error keys inside data
                    # (e.g. register entries) are left untouched.
                    outcome = ("value_error", str(result["error"]))
                else:
                    outcome = ("ok", result)
            except Exception as e:
                outcome = ("error", str(e))

            with self._abandoned_lock:
                abandoned = request_id in self._abandoned
                self._abandoned.discard(request_id)

            if abandoned:
                # The client already received a timeout. The callback cannot be
                # un-posted, so make the dropped late result visible.
                gdb.write(
                    f"[GDBRPCServer] Late result for abandoned request "
                    f"{request_id} dropped\n"
                )
                return

            result_queue.put(outcome)

        gdb.post_event(run_handler)

        try:
            status, result = result_queue.get(timeout=self.command_timeout)
        except queue.Empty:
            with self._abandoned_lock:
                self._abandoned.add(request_id)
            raise RuntimeError(
                f"Command '{cmd}' timed out after {self.command_timeout:g}s "
                f"(request {request_id})"
            )

        if status == "value_error":
            raise ValueError(str(result))
        if status == "error":
            raise RuntimeError(str(result))

        return result

    def _start_heartbeat_timer(self) -> None:
        """(Re)arm the heartbeat timer.

        A non-positive ``heartbeat_timeout`` disables idle auto-detach
        entirely (no timer is started).
        """
        if self.heartbeat_timeout <= 0:
            if self.heartbeat_timer:
                self.heartbeat_timer.cancel()
                self.heartbeat_timer = None
            return

        with self._heartbeat_lock:
            self._heartbeat_generation += 1
            generation = self._heartbeat_generation

            if self.heartbeat_timer:
                self.heartbeat_timer.cancel()

            self.heartbeat_timer = threading.Timer(
                self.heartbeat_timeout,
                self._heartbeat_timeout,
                args=(generation,),
            )
            self.heartbeat_timer.daemon = True
            self.heartbeat_timer.start()

    def _reset_heartbeat(self) -> None:
        """每次收到请求后重置心跳计时器"""
        self.last_active = time.time()
        self._start_heartbeat_timer()

    def _heartbeat_timeout(self, generation: Optional[int] = None) -> None:
        """Handle a heartbeat timeout.

        This runs on the Timer thread. It only *validates* conditions and posts
        the actual GDB work (and all ``gdb.write`` calls) to the main thread.
        The generation guard ensures a stale timer that fires after a newer
        request reset the heartbeat does nothing.
        """
        if not self.running:
            return
        if generation is not None and generation != self._heartbeat_generation:
            return
        if self.heartbeat_timeout > 0 and (
            time.time() - self.last_active
        ) < self.heartbeat_timeout:
            return

        def do_cleanup():
            # Re-check on the main thread: a request may have arrived while
            # the event was queued.
            if not self.running:
                return
            if generation is not None and generation != self._heartbeat_generation:
                return
            if self.heartbeat_timeout > 0 and (
                time.time() - self.last_active
            ) < self.heartbeat_timeout:
                return

            gdb.write(
                f"[GDBRPCServer] Heartbeat timeout "
                f"({self.heartbeat_timeout}s), detaching...\n"
            )

            errors = []
            try:
                inferiors = list(gdb.inferiors())
            except Exception as e:
                inferiors = []
                errors.append(f"cannot list inferiors: {e}")

            for inferior in inferiors:
                if not getattr(inferior, "pid", None):
                    continue
                num = getattr(inferior, "num", None)
                try:
                    gdb.execute(f"detach inferiors {num}", to_string=True)
                except Exception as e:
                    # Fall back to plain detach if the inferior selector is
                    # unavailable (e.g. older GDB or a already-gone inferior).
                    try:
                        gdb.execute("detach", to_string=True)
                    except Exception as fallback_error:
                        errors.append(
                            f"detach inferior {num}: {e}; "
                            f"fallback detach: {fallback_error}"
                        )

            if errors:
                gdb.write(
                    "[GDBRPCServer] Cleanup errors: "
                    + "; ".join(errors)
                    + "\n"
                )

            try:
                gdb.execute("quit", to_string=True)
            except Exception as e:
                gdb.write(f"[GDBRPCServer] Cleanup error: {e}\n")
                # 清理 socket 文件后强制退出
                try:
                    if self.sock_path.exists():
                        self.sock_path.unlink()
                except Exception:
                    pass
                os._exit(0)

        gdb.post_event(do_cleanup)

    def _loading_timeout(self) -> None:
        """加载超时处理：将会话标记为 error 状态。"""
        if self._state != "loading":
            return

        self._state = "error"
        self._error_reason = (
            f"Loading timeout ({self.LOADING_TIMEOUT:.0f}s), "
            "session marked as error"
        )

        def report() -> None:
            # gdb.write is not safe from the Timer thread.
            gdb.write(
                f"[GDBRPCServer] Loading timeout "
                f"({self.LOADING_TIMEOUT:.0f}s), session marked as error\n"
            )

        gdb.post_event(report)


def start_server(sock_path: str, session_meta: dict, heartbeat_timeout: int = 600) -> GDBRPCServer:
    """
    启动 GDB RPC Server 的便捷函数

    在 GDB 中通过 source 加载后调用:
    ```
    source /path/to/gdb_rpc_server.py
    python start_server("/tmp/gdb.sock", {"mode": "core", "binary": "./a.out"})
    ```
    """
    server = GDBRPCServer(sock_path, session_meta, heartbeat_timeout)
    server.start()

    import __main__
    __main__._gdb_rpc_server = server

    # 注册 before_prompt 事件来处理 post_event
    # 这样 GDB 在等待输入时会处理事件
    def process_events():
        pass  # post_event 的事件会在 before_prompt 时被处理

    gdb.events.before_prompt.connect(process_events)

    return server


# GDB 启动时自动初始化 (如果环境变量指定了配置)
def _auto_init() -> None:
    """
    从环境变量读取配置并自动启动

    环境变量:
    - GDB_CLI_SOCK_PATH: Socket 路径
    - GDB_CLI_SESSION_META: JSON 格式的 session 元数据
    - GDB_CLI_HEARTBEAT: 心跳超时秒数
    """
    sock_path = os.environ.get("GDB_CLI_SOCK_PATH")
    meta_json = os.environ.get("GDB_CLI_SESSION_META")
    heartbeat = os.environ.get("GDB_CLI_HEARTBEAT", "600")

    if sock_path and meta_json and GDB_AVAILABLE:
        try:
            session_meta = json.loads(meta_json)
            heartbeat_timeout = int(heartbeat)
            start_server(sock_path, session_meta, heartbeat_timeout)
        except Exception as e:
            gdb.write(f"[GDBRPCServer] Auto-init failed: {e}\n")


# 延迟初始化 (在 GDB 完全加载后)
if GDB_AVAILABLE:
    gdb.events.new_objfile.connect(lambda _: None)  # 占位，确保 events 可用
    # 实际自动初始化由 launcher 通过 -ex 调用 start_server
