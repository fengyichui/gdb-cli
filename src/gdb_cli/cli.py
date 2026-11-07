"""
GDB CLI - 命令行入口

Usage:
    gdb-cli load --binary ./my_program --core ./core.1234
    gdb-cli attach --pid 9876
    gdb-cli target --remote 192.168.0.21:3333
    gdb-cli eval-cmd --session <id> "lock_mgr->buckets[0]"
    gdb-cli threads --session <id> [--limit 20]
    gdb-cli bt --session <id> [--thread 12] [--limit 30]
    gdb-cli stop --session <id>
"""


import json
import os
import re
import time
import uuid
from typing import Optional

import click

from . import __version__
from .client import GDBClient, GDBClientError, GDBCommandError
from .i18n import t
from .jlink import (
    JLINK_DIR,
    JLinkManagerError,
    build_gdbserver_cmdline,
    enumerate_usb_devices,
    find_free_port,
    get_instance,
    list_instances,
    restart_instance,
    start_gdbserver,
    stop_instance,
    validate_select,
)
from .launcher import GDBLauncherError, launch_attach, launch_core, launch_target
from .session import (
    _read_proc_starttime,
    cleanup_dead_sessions,
    find_session_by_core,
    find_session_by_pid,
    find_session_by_remote,
    get_session,
    list_sessions,
)
from .signal_handlers import setup_signal_handlers


def print_json(data: dict) -> None:
    """Format JSON output. "status"/"state" fields are stable machine-readable codes; "message" is human-facing and locale-dependent."""
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def print_error(message: str, details: Optional[str] = None) -> None:
    """输出错误信息"""
    error = {"error": message}
    if details:
        error["details"] = details
    click.echo(json.dumps(error, indent=2), err=True)


def get_client(session_id: str) -> GDBClient:
    """获取会话的客户端"""
    session = get_session(session_id)
    if session is None:
        raise click.ClickException(t("errors.session_not_found", session_id=session_id))

    if session.sock_path is None:
        raise click.ClickException(t("errors.session_no_socket", session_id=session_id))

    return GDBClient(str(session.sock_path))


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """GDB CLI for AI - Thin client CLI + GDB built-in Python RPC Server"""
    setup_signal_handlers()
    pass


@main.command()
@click.option("--binary", "-b", required=True, help=t("cli.load.binary_help"))
@click.option("--core", "-c", required=True, help=t("cli.load.core_help"))
@click.option("--sysroot", help=t("cli.load.sysroot_help"))
@click.option("--solib-prefix", help=t("cli.load.solib_prefix_help"))
@click.option("--source-dir", help=t("cli.load.source_dir_help"))
@click.option("--timeout", default=600, help=t("cli.load.timeout_help"))
@click.option("--gdb-path", default="gdb", help=t("cli.load.gdb_path_help"))
def load(
    binary: str,
    core: str,
    sysroot: Optional[str],
    solib_prefix: Optional[str],
    source_dir: Optional[str],
    timeout: int,
    gdb_path: str
) -> None:
    """Load core dump and start persistent GDB process"""
    # 检查是否已有相同 core 的会话
    existing = find_session_by_core(core)
    if existing:
        print_json({
            "session_id": existing.session_id,
            "mode": existing.mode,
            "binary": existing.binary,
            "core": existing.core,
            "status": "reused",
            "message": t("cli.load.session_reused_message")
        })
        return

    try:
        gdb_process = launch_core(
            binary=binary,
            core=core,
            sysroot=sysroot,
            solib_prefix=solib_prefix,
            source_dir=source_dir,
            timeout=timeout,
            gdb_path=gdb_path
        )

        session = gdb_process.session

        print_json({
            "session_id": session.session_id,
            "mode": session.mode,
            "binary": session.binary,
            "core": session.core,
            "sock_path": session.sock_path,
            "gdb_pid": gdb_process.pid,
            "status": "loading"
        })

    except GDBLauncherError as e:
        print_error(t("cli.load.failed"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--pid", "-p", required=True, type=int, help=t("cli.attach.pid_help"))
@click.option("--binary", "-b", help=t("cli.attach.binary_help"))
@click.option("--scheduler-locking/--no-scheduler-locking", default=True, help=t("cli.attach.scheduler_locking_help"))
@click.option("--non-stop/--no-non-stop", default=True, help=t("cli.attach.non_stop_help"))
@click.option("--timeout", default=600, help=t("cli.attach.timeout_help"))
@click.option("--allow-write", is_flag=True, help=t("cli.attach.allow_write_help"))
@click.option("--allow-call", is_flag=True, help=t("cli.attach.allow_call_help"))
def attach(
    pid: int,
    binary: Optional[str],
    scheduler_locking: bool,
    non_stop: bool,
    timeout: int,
    allow_write: bool,
    allow_call: bool
) -> None:
    """Attach to running process"""
    # 检查是否已有相同 PID 的会话 (幂等性)
    existing = find_session_by_pid(pid)
    if existing:
        print_json({
            "session_id": existing.session_id,
            "mode": existing.mode,
            "pid": existing.pid,
            "status": "reused",
            "message": t("cli.attach.session_reused_message")
        })
        return

    try:
        gdb_process = launch_attach(
            pid=pid,
            binary=binary,
            scheduler_locking=scheduler_locking,
            non_stop=non_stop,
            timeout=timeout,
            allow_write=allow_write,
            allow_call=allow_call
        )

        session = gdb_process.session

        print_json({
            "session_id": session.session_id,
            "mode": session.mode,
            "pid": session.pid,
            "binary": session.binary,
            "sock_path": session.sock_path,
            "gdb_pid": gdb_process.pid,
            "safety_level": session.safety_level,
            "status": "started"
        })

    except GDBLauncherError as e:
        print_error(t("cli.attach.failed"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--remote", "-r", required=True, type=str, help=t("cli.target.remote_help"))
@click.option("--binary", "-b", help=t("cli.target.binary_help"))
@click.option(
    "--remote-mode",
    type=click.Choice(["remote", "extended-remote"]),
    default="extended-remote",
    help=t("cli.target.remote_mode_help"),
)
@click.option("--scheduler-locking/--no-scheduler-locking", default=False, help=t("cli.target.scheduler_locking_help"))
@click.option("--non-stop/--no-non-stop", default=False, help=t("cli.target.non_stop_help"))
@click.option("--timeout", default=600, help=t("cli.target.timeout_help"))
@click.option("--allow-write", is_flag=True, help=t("cli.target.allow_write_help"))
@click.option("--allow-call", is_flag=True, help=t("cli.target.allow_call_help"))
@click.option("--gdb-path", default="gdb", help=t("cli.load.gdb_path_help"))
def target(
    remote: str,
    binary: Optional[str],
    remote_mode: str,
    scheduler_locking: bool,
    non_stop: bool,
    timeout: int,
    allow_write: bool,
    allow_call: bool,
    gdb_path: str,
) -> None:
    """Connect to remote GDB server"""
    # host:port, or a bracketed IPv6 address such as [::1]:2331.
    if not re.match(r'^(?:[\w.-]+|\[[0-9A-Fa-f:.]+\]):\d+$', remote):
        print_error(t("cli.target.invalid_format", remote=remote))
        raise click.exceptions.Exit(1)

    existing = find_session_by_remote(remote)
    if existing:
        print_json({
            "session_id": existing.session_id,
            "mode": existing.mode,
            "remote": existing.remote,
            "status": "reused",
            "message": t("cli.target.session_reused_message")
        })
        return

    try:
        gdb_process = launch_target(
            remote=remote,
            binary=binary,
            remote_mode=remote_mode,
            scheduler_locking=scheduler_locking,
            non_stop=non_stop,
            timeout=timeout,
            allow_write=allow_write,
            allow_call=allow_call,
            gdb_path=gdb_path
        )

        session = gdb_process.session

        print_json({
            "session_id": session.session_id,
            "mode": session.mode,
            "remote": session.remote,
            "binary": session.binary,
            "sock_path": session.sock_path,
            "gdb_pid": gdb_process.pid,
            "safety_level": session.safety_level,
            "status": "started"
        })

    except GDBLauncherError as e:
        print_error(t("cli.target.failed"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.eval_cmd.session_help"))
@click.argument("expr")
@click.option("--max-depth", default=3, help=t("cli.eval_cmd.max_depth_help"))
@click.option("--max-elements", default=50, help=t("cli.eval_cmd.max_elements_help"))
@click.option("--deref", is_flag=True, help=t("cli.eval_cmd.deref_help"))
def eval_cmd(
    session: str,
    expr: str,
    max_depth: int,
    max_elements: int,
    deref: bool,
) -> None:
    """Evaluate C/C++ expression"""
    try:
        with get_client(session) as client:
            result = client.eval(
                expr,
                max_depth=max_depth,
                max_elements=max_elements,
                deref=deref,
            )
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e), expr)
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.threads.session_help"))
@click.option("--range", "range_str", help=t("cli.threads.range_help"))
@click.option("--limit", default=20, help=t("cli.threads.limit_help"))
@click.option("--filter-state", help=t("cli.threads.filter_state_help"))
def threads(session: str, range_str: Optional[str], limit: int, filter_state: Optional[str]) -> None:
    """List threads"""
    try:
        with get_client(session) as client:
            result = client.threads(range_str=range_str, limit=limit, filter_state=filter_state)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.bt.session_help"))
@click.option("--thread", "-t", "thread_id", type=int, help=t("cli.bt.thread_help"))
@click.option("--limit", default=30, help=t("cli.bt.limit_help"))
@click.option("--full", is_flag=True, help=t("cli.bt.full_help"))
@click.option("--range", "range_str", help=t("cli.bt.range_help"))
def bt(session: str, thread_id: Optional[int], limit: int, full: bool, range_str: Optional[str]) -> None:
    """Get backtrace"""
    try:
        with get_client(session) as client:
            params = {"limit": limit, "full": full}
            if thread_id is not None:
                params["thread_id"] = thread_id
            if range_str:
                params["range_str"] = range_str
            result = client.call("bt", **params)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command("frame")
@click.option("--session", "-s", required=True, help=t("cli.frame.session_help"))
@click.argument("number", type=int)
def frame_cmd(session: str, number: int) -> None:
    """Select stack frame"""
    try:
        with get_client(session) as client:
            result = client.frame_select(number)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.locals_cmd.session_help"))
@click.option("--thread", "-t", "thread_id", type=int, help=t("cli.locals_cmd.thread_help"))
@click.option("--frame", "-f", default=0, help=t("cli.locals_cmd.frame_help"))
def locals_cmd(session: str, thread_id: Optional[int], frame: int) -> None:
    """Get local variables"""
    try:
        with get_client(session) as client:
            result = client.locals(thread_id=thread_id, frame=frame)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command("exec")
@click.option("--session", "-s", required=True, help=t("cli.exec.session_help"))
@click.argument("command")
def exec_cmd(session: str, command: str) -> None:
    """Execute raw GDB command"""
    try:
        with get_client(session) as client:
            result = client.exec_cmd(command)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e), command)
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.stop.session_help"))
@click.option("--before-detach", help=t("cli.stop.before_detach_help"))
@click.option("--force", is_flag=True, help=t("cli.stop.force_help"))
def stop(session: str, before_detach: Optional[str], force: bool) -> None:
    """Stop session and safely exit GDB"""
    try:
        # 发送停止命令；Server 先 detach，再在响应返回后退出 GDB
        with get_client(session) as client:
            result = client.call("stop", before_detach=before_detach or "")
    except GDBClientError as e:
        if not force:
            print_error(t("errors.connection_error"), str(e))
            raise click.exceptions.Exit(1)

        # Explicit --force: fall back to the old hard cleanup path.
        from .session import cleanup_session
        if not cleanup_session(session):
            print_error(t("cli.stop.cleanup_failed", session_id=session), session)
            raise click.exceptions.Exit(1)
        print_json({
            "session_id": session,
            "status": "force_stopped"
        })
        return

    # Graceful path: give the GDB process time to exit on its own before
    # falling back to cleanup_session (which sends SIGTERM/SIGKILL).
    meta = get_session(session)
    if meta is not None and meta.gdb_pid:
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                os.kill(meta.gdb_pid, 0)
            except OSError:
                break
            time.sleep(0.1)

    from .session import cleanup_session
    if not cleanup_session(session):
        print_error(t("cli.stop.cleanup_failed", session_id=session), session)
        raise click.exceptions.Exit(1)

    output = {
        "session_id": session,
        "status": "stopped",
        "detached": bool(result.get("detached")),
    }
    if result.get("errors"):
        output["detach_errors"] = result["errors"]
    print_json(output)


@main.command()
def sessions() -> None:
    """List all active sessions"""
    # 清理僵尸会话
    cleanup_dead_sessions()

    session_list = list_sessions(alive_only=True)

    result = {
        "sessions": [
            {
                "session_id": s.session_id,
                "mode": s.mode,
                "binary": s.binary,
                "pid": s.gdb_pid,
                "remote": s.remote,
                "core": s.core,
                "gdb_pid": s.gdb_pid,
                "started_at": s.started_at,
            }
            for s in session_list
        ],
        "count": len(session_list)
    }

    print_json(result)


def _format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}s"
    elif total < 3600:
        m, s = divmod(total, 60)
        return f"{m}m{s}s"
    else:
        h, remainder = divmod(total, 3600)
        m = remainder // 60
        return f"{h}h{m}m"


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.status.session_help"))
def status(session: str) -> None:
    """Check session status"""
    try:
        with get_client(session) as client:
            result = client.status()
            result["session_id"] = session
            if result.get("state") == "loading" and isinstance(result.get("elapsed"), (int, float)):
                result["elapsed"] = _format_elapsed(result["elapsed"])
            print_json(result)
    except GDBClientError as e:
        meta = get_session(session)
        if meta is None:
            print_error(t("errors.session_not_found", session_id=session))
            raise click.exceptions.Exit(1)

        if meta.gdb_pid:
            try:
                os.kill(meta.gdb_pid, 0)
                elapsed = time.time() - meta.started_at
                if elapsed > 120:
                    # A live process that still cannot answer after two minutes
                    # is no longer plausibly "loading".
                    result = {
                        "session_id": session,
                        "state": "unresponsive",
                        "message": t("cli.status.gdb_unresponsive_message"),
                        "error": str(e),
                    }
                else:
                    result = {
                        "session_id": session,
                        "state": "loading",
                        "message": t("cli.status.gdb_loading_message"),
                    }
                result["elapsed"] = _format_elapsed(elapsed)
                print_json(result)
                return
            except OSError:
                print_error(t("cli.status.session_dead"), t("cli.status.gdb_process_dead", pid=meta.gdb_pid))
                raise click.exceptions.Exit(1)

        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command("eval-element")
@click.option("--session", "-s", required=True, help=t("cli.eval_element.session_help"))
@click.argument("expr")
@click.option("--index", "-i", required=True, type=int, help=t("cli.eval_element.index_help"))
@click.option("--max-depth", default=3, help=t("cli.eval_element.max_depth_help"))
def eval_element_cmd(session: str, expr: str, index: int, max_depth: int) -> None:
    """Access array/container element"""
    try:
        with get_client(session) as client:
            result = client.call("eval_element", expr=expr, index=index, max_depth=max_depth)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e), f"{expr}[{index}]")
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command("thread-apply")
@click.option("--session", "-s", required=True, help=t("cli.thread_apply.session_help"))
@click.argument("command")
@click.option("--threads", help=t("cli.thread_apply.threads_help"))
@click.option("--all", "all_threads", is_flag=True, help=t("cli.thread_apply.all_help"))
def thread_apply_cmd(session: str, command: str, threads: Optional[str], all_threads: bool) -> None:
    """Batch thread operations"""
    try:
        with get_client(session) as client:
            params = {"command": command}
            if all_threads:
                params["all_threads"] = True
            elif threads:
                params["thread_ids"] = threads
            else:
                print_error(t("cli.thread_apply.require_target"))
                raise click.exceptions.Exit(1)
            result = client.call("thread_apply", **params)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e), command)
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.args.session_help"))
@click.option("--thread", "-t", "thread_id", type=int, help=t("cli.args.thread_help"))
@click.option("--frame", "-f", default=0, help=t("cli.args.frame_help"))
def args(session: str, thread_id: Optional[int], frame: int) -> None:
    """Get function arguments"""
    try:
        with get_client(session) as client:
            params = {"frame": frame}
            if thread_id is not None:
                params["thread_id"] = thread_id
            result = client.call("args", **params)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.registers.session_help"))
@click.option("--names", "-n", help=t("cli.registers.names_help"))
@click.option("--thread", "-t", "thread_id", type=int, help=t("cli.registers.thread_help"))
@click.option("--frame", "-f", default=0, help=t("cli.registers.frame_help"))
def registers(session: str, names: Optional[str], thread_id: Optional[int], frame: int) -> None:
    """View register values"""
    try:
        with get_client(session) as client:
            params = {"frame": frame}
            if names:
                params["names"] = names
            if thread_id is not None:
                params["thread_id"] = thread_id
            result = client.call("registers", **params)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.memory.session_help"))
@click.argument("address")
@click.option("--size", default=64, help=t("cli.memory.size_help"))
@click.option("--fmt", default="hex", type=click.Choice(["hex", "bytes", "string"]), help=t("cli.memory.fmt_help"))
def memory(session: str, address: str, size: int, fmt: str) -> None:
    """Inspect memory content"""
    try:
        with get_client(session) as client:
            result = client.call("memory", address=address, size=size, fmt=fmt)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e), address)
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.ptype.session_help"))
@click.argument("expr")
def ptype(session: str, expr: str) -> None:
    """View type information for expression"""
    try:
        with get_client(session) as client:
            result = client.call("ptype", expr=expr)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e), expr)
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command("thread-switch")
@click.option("--session", "-s", required=True, help=t("cli.thread_switch.session_help"))
@click.argument("thread_id", type=int)
def thread_switch_cmd(session: str, thread_id: int) -> None:
    """Switch current thread"""
    try:
        with get_client(session) as client:
            result = client.call("thread_switch", thread_id=thread_id)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command("up")
@click.option("--session", "-s", required=True, help=t("cli.up.session_help"))
@click.argument("count", type=int, default=1)
def frame_up_cmd(session: str, count: int) -> None:
    """Move toward caller in stack"""
    try:
        with get_client(session) as client:
            result = client.call("frame", number=count, direction="up")
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command("down")
@click.option("--session", "-s", required=True, help=t("cli.down.session_help"))
@click.argument("count", type=int, default=1)
def frame_down_cmd(session: str, count: int) -> None:
    """Move toward callee in stack"""
    try:
        with get_client(session) as client:
            result = client.call("frame", number=count, direction="down")
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.sharedlibs.session_help"))
def sharedlibs(session: str) -> None:
    """View loaded shared libraries"""
    try:
        with get_client(session) as client:
            result = client.call("sharedlibs")
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--session", "-s", required=True, help=t("cli.disasm.session_help"))
@click.option("--start", help=t("cli.disasm.start_help"))
@click.option("--count", default=20, help=t("cli.disasm.count_help"))
@click.option("--thread", "-t", "thread_id", type=int, help=t("cli.disasm.thread_help"))
@click.option("--frame", "-f", default=0, help=t("cli.disasm.frame_help"))
def disasm(session: str, start: Optional[str], count: int, thread_id: Optional[int], frame: int) -> None:
    """Disassemble"""
    try:
        with get_client(session) as client:
            params = {"count": count, "frame": frame}
            if start:
                params["start"] = start
            if thread_id is not None:
                params["thread_id"] = thread_id
            result = client.call("disasm", **params)
            print_json(result)
    except GDBCommandError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)
    except GDBClientError as e:
        print_error(t("errors.connection_error"), str(e))
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--gdb-path", default=None, help=t("cli.load.gdb_path_help"))
def env_check(gdb_path) -> None:
    """Environment check: GDB version, ptrace permissions, Python version"""
    from .env_check import get_env_check_cli_output
    results = get_env_check_cli_output(gdb_path=gdb_path)
    print_json(results)


def _jlink_start_options(func):
    """Attach the options shared by ``jlink`` and ``jlink start``."""
    func = click.option(
        "--extra-arg", "extra_args", multiple=True,
        help=t("cli.jlink.extra_arg_help")
    )(func)
    func = click.option("--timeout", default=600, help=t("cli.jlink.timeout_help"))(func)
    func = click.option(
        "--allow-call", is_flag=True, help=t("cli.jlink.allow_call_help")
    )(func)
    func = click.option(
        "--allow-write", is_flag=True, help=t("cli.jlink.allow_write_help")
    )(func)
    func = click.option("--port", type=int, default=None, help=t("cli.jlink.port_help"))(func)
    func = click.option(
        "--if", "interface", default="SWD", help=t("cli.jlink.interface_help")
    )(func)
    func = click.option("--speed", default=None, help=t("cli.jlink.speed_help"))(func)
    func = click.option(
        "--jlink-path", default="JLinkGDBServer", help=t("cli.jlink.jlink_path_help")
    )(func)
    func = click.option(
        "--gdb-path", default="gdb", help=t("cli.jlink.gdb_path_help")
    )(func)
    func = click.option(
        "--binary", "-b", default=None, help=t("cli.jlink.binary_help")
    )(func)
    func = click.option("--select", default=None, help=t("cli.jlink.select_help"))(func)
    func = click.option(
        "--device", "-d", default=None, help=t("cli.jlink.device_help")
    )(func)
    return func


def _resolve_instance_id(instance_id: Optional[str]) -> str:
    """Return the requested id, or the only running one when unambiguous."""
    if instance_id:
        return instance_id

    instances = list_instances()
    if not instances:
        raise JLinkManagerError(t("cli.jlink.no_instances"))
    if len(instances) > 1:
        ids = ", ".join(instance.instance_id for instance in instances)
        raise JLinkManagerError(
            t("cli.jlink.ambiguous_instance", instances=ids)
        )
    return instances[0].instance_id


@main.group(invoke_without_command=True, help=t("cli.jlink.doc"))
@_jlink_start_options
def jlink(
    device: Optional[str],
    select: Optional[str],
    binary: Optional[str],
    gdb_path: str,
    jlink_path: str,
    speed: Optional[str],
    interface: str,
    port: Optional[int],
    allow_write: bool,
    allow_call: bool,
    timeout: int,
    extra_args,
) -> None:
    """Manage JLinkGDBServer and automatically start a GDB session"""
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is not None:
        return

    if device is None:
        click.echo(ctx.get_help())
        return

    # ``gdb-cli jlink -d DEV --select ...`` defaults to the ``start`` command.
    ctx.invoke(
        jlink_start,
        device=device,
        select=select,
        binary=binary,
        gdb_path=gdb_path,
        jlink_path=jlink_path,
        speed=speed,
        interface=interface,
        port=port,
        allow_write=allow_write,
        allow_call=allow_call,
        timeout=timeout,
        extra_args=extra_args,
    )


@jlink.command("start", help=t("cli.jlink.start.doc"))
@_jlink_start_options
def jlink_start(
    device: Optional[str],
    select: Optional[str],
    binary: Optional[str],
    gdb_path: str,
    jlink_path: str,
    speed: Optional[str],
    interface: str,
    port: Optional[int],
    allow_write: bool,
    allow_call: bool,
    timeout: int,
    extra_args,
) -> None:
    """Start JLinkGDBServer and connect GDB"""
    try:
        if not device:
            raise JLinkManagerError(t("cli.jlink.device_required"))
        validate_select(select or "")
    except JLinkManagerError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)

    if port is None:
        port = find_free_port()

    cmdline = build_gdbserver_cmdline(
        device=device,
        select=select or "",
        port=port,
        speed=speed,
        interface=interface,
        extra_args=list(extra_args or ()),
        jlink_exe=jlink_path,
    )

    jlink_id = uuid.uuid4().hex[:8]
    log_path = str(JLINK_DIR / f"{jlink_id}.log")

    try:
        instance = start_gdbserver(cmdline, log_path, instance_id=jlink_id)
    except JLinkManagerError as e:
        print_error(t("cli.jlink.start_failed"), str(e))
        raise click.exceptions.Exit(1)

    try:
        gdb_process = launch_target(
            remote=f"127.0.0.1:{instance.port}",
            binary=binary,
            timeout=timeout,
            allow_write=allow_write,
            allow_call=allow_call,
            gdb_path=gdb_path,
        )
    except GDBLauncherError as e:
        # Do not leave an orphan GDBServer behind when GDB cannot attach.
        stop_instance(instance.instance_id)
        print_error(t("cli.jlink.connect_failed"), str(e))
        raise click.exceptions.Exit(1)
    except Exception as e:
        stop_instance(instance.instance_id)
        print_error(t("cli.jlink.connect_failed"), str(e))
        raise click.exceptions.Exit(1)

    print_json({
        "jlink_id": instance.instance_id,
        "port": instance.port,
        "device": instance.device,
        "select": instance.select,
        "session_id": gdb_process.session.session_id,
        "status": "started",
    })


@jlink.command("stop", help=t("cli.jlink.stop.doc"))
@click.option("--jlink-id", "-s", default=None, help=t("cli.jlink.jlink_id_help"))
@click.option("--all", "all_instances", is_flag=True, help=t("cli.jlink.all_help"))
def jlink_stop(jlink_id: Optional[str], all_instances: bool) -> None:
    """Stop JLinkGDBServer instance(s)"""
    try:
        if all_instances:
            instances = list_instances()
            if not instances:
                raise JLinkManagerError(t("cli.jlink.no_instances"))
            results = [stop_instance(instance.instance_id) for instance in instances]
            print_json({
                "stopped": results,
                "count": len(results),
                "status": "stopped",
            })
            return

        resolved = _resolve_instance_id(jlink_id)
        result = stop_instance(resolved)
        result["status"] = "stopped"
        print_json(result)
    except JLinkManagerError as e:
        print_error(t("cli.jlink.stop_failed"), str(e))
        raise click.exceptions.Exit(1)


@jlink.command("restart", help=t("cli.jlink.restart.doc"))
@click.option("--jlink-id", "-s", default=None, help=t("cli.jlink.jlink_id_help"))
def jlink_restart(jlink_id: Optional[str]) -> None:
    """Restart a JLinkGDBServer instance"""
    try:
        resolved = _resolve_instance_id(jlink_id)
        instance = restart_instance(resolved)
    except JLinkManagerError as e:
        print_error(t("cli.jlink.restart_failed"), str(e))
        raise click.exceptions.Exit(1)

    print_json({
        "jlink_id": instance.instance_id,
        "port": instance.port,
        "device": instance.device,
        "select": instance.select,
        "status": "restarted",
    })


@jlink.command("status", help=t("cli.jlink.status.doc"))
@click.option("--jlink-id", "-s", default=None, help=t("cli.jlink.jlink_id_help"))
def jlink_status(jlink_id: Optional[str]) -> None:
    """Show JLinkGDBServer instance status"""
    try:
        if jlink_id:
            instance = get_instance(jlink_id)
            if instance is None:
                raise JLinkManagerError(
                    t("cli.jlink.no_instance", instance_id=jlink_id)
                )
            instances = [instance]
        else:
            instances = list_instances()
    except JLinkManagerError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)

    entries = []
    for instance in instances:
        current_start_time = (
            _read_proc_starttime(instance.pid) if instance.pid else None
        )
        running = (
            current_start_time is not None
            and instance.start_time is not None
            and current_start_time == instance.start_time
        )
        entries.append({
            "jlink_id": instance.instance_id,
            "port": instance.port,
            "device": instance.device,
            "select": instance.select,
            "pid": instance.pid,
            "log_path": instance.log_path,
            "started_at": instance.started_at,
            "running": running,
        })

    print_json({"instances": entries, "count": len(entries)})


@jlink.command("devices", help=t("cli.jlink.devices.doc"))
def jlink_devices() -> None:
    """List attached J-Link probes"""
    try:
        devices = enumerate_usb_devices()
    except JLinkManagerError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)

    print_json({"devices": devices, "count": len(devices)})


if __name__ == "__main__":
    main()
