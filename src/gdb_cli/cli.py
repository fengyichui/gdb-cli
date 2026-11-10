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
    _save_instance,
    _validate_extra_args,
    build_gdbserver_cmdline,
    delete_instance_metadata,
    enumerate_usb_devices,
    find_free_port,
    get_instance,
    list_instances,
    start_gdbserver,
    stop_instance,
    validate_select,
)
from .launcher import GDBLauncherError, launch_attach, launch_core, launch_target
from .session import (
    cleanup_dead_sessions,
    cleanup_session,
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


def print_error(
    message: str,
    details: Optional[str] = None,
    cleanup_errors: Optional[list] = None,
) -> None:
    """输出错误信息"""
    error = {"error": message}
    if details:
        error["details"] = details
    if cleanup_errors:
        error["cleanup_errors"] = cleanup_errors
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
def attach(
    pid: int,
    binary: Optional[str],
    scheduler_locking: bool,
    non_stop: bool,
    timeout: int
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
            timeout=timeout
        )

        session = gdb_process.session

        print_json({
            "session_id": session.session_id,
            "mode": session.mode,
            "pid": session.pid,
            "binary": session.binary,
            "sock_path": session.sock_path,
            "gdb_pid": gdb_process.pid,
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
@click.option("--gdb-path", default="gdb", help=t("cli.load.gdb_path_help"))
def target(
    remote: str,
    binary: Optional[str],
    remote_mode: str,
    scheduler_locking: bool,
    non_stop: bool,
    timeout: int,
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


def _stop_bound_jlink_instances(session_id: str):
    """Stop JLink servers whose persisted ``session_id`` matches."""
    stopped = []
    errors = []
    for instance in list_instances():
        if instance.session_id != session_id:
            continue
        try:
            result = stop_instance(instance.instance_id)
            if result.get("status") == "stop_failed":
                errors.append(
                    f"JLinkGDBServer {instance.instance_id} did not stop"
                )
            else:
                stopped.append(result)
        except Exception as exc:
            errors.append(f"stop_instance {instance.instance_id}: {exc}")
    return stopped, errors


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
        jlink_stopped, jlink_errors = _stop_bound_jlink_instances(session)
        payload = {
            "session_id": session,
            "status": "force_stopped"
        }
        if jlink_stopped:
            payload["jlink"] = jlink_stopped
        if jlink_errors:
            payload["jlink_errors"] = jlink_errors
        print_json(payload)
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

    jlink_stopped, jlink_errors = _stop_bound_jlink_instances(session)
    output = {
        "session_id": session,
        "status": "stopped",
        "detached": bool(result.get("detached")),
    }
    if result.get("errors"):
        output["detach_errors"] = result["errors"]
    if jlink_stopped:
        output["jlink"] = jlink_stopped
    if jlink_errors:
        output["jlink_errors"] = jlink_errors
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


# Real click provides IntRange; the test-suite's FakeClick shims may not, in
# which case a plain int is enough for import-time decoration only.
_ClickIntRange = getattr(click, "IntRange", None)
_PORT_TYPE = _ClickIntRange(1, 65535) if _ClickIntRange is not None else int


def _jlink_start_options(func):
    """Attach the options shared by ``jlink`` and ``jlink start``."""
    func = click.option(
        "--extra-arg", "extra_args", multiple=True,
        help=t("cli.jlink.extra_arg_help")
    )(func)
    func = click.option("--timeout", default=600, help=t("cli.jlink.timeout_help"))(func)
    func = click.option(
        "--init-cmd", "init_cmds", multiple=True,
        help=t("cli.jlink.init_cmd_help")
    )(func)
    func = click.option(
        "--port", type=_PORT_TYPE, default=None,
        help=t("cli.jlink.port_help"),
    )(func)
    func = click.option(
        "--if", "interface", default="SWD", help=t("cli.jlink.interface_help")
    )(func)
    func = click.option("--speed", default=None, help=t("cli.jlink.speed_help"))(func)
    func = click.option("--rtos", default=None, help=t("cli.jlink.rtos_help"))(func)
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


_JLINK_START_OPTION_NAMES = (
    "device",
    "select",
    "binary",
    "gdb_path",
    "jlink_path",
    "speed",
    "rtos",
    "interface",
    "port",
    "timeout",
    "init_cmds",
    "extra_args",
)

_SESSION_READY_POLL_INTERVAL = 0.2


def _is_commandline(source) -> bool:
    """True when a click ``ParameterSource`` came from the command line.

    Compares by enum name so this module can still be imported under the
    FakeClick shim used by the test-suite.
    """
    return getattr(source, "name", source) == "COMMANDLINE"


def _merge_group_params(ctx, names=_JLINK_START_OPTION_NAMES) -> dict:
    """Merge group-level and subcommand-level ``jlink`` options.

    Precedence: explicit subcommand command line > explicit group command line
    > subcommand default.  When the context cannot be introspected (direct
    callback invocation, tests) an empty dict is returned and the caller keeps
    the values it was already called with.
    """
    params = getattr(ctx, "params", None)
    get_source = getattr(ctx, "get_parameter_source", None)
    if not isinstance(params, dict) or not callable(get_source):
        return {}

    parent = getattr(ctx, "parent", None)
    parent_params = getattr(parent, "params", None)
    parent_get_source = getattr(parent, "get_parameter_source", None)

    merged = {}
    for name in names:
        value = params.get(name)
        if _is_commandline(get_source(name)):
            merged[name] = value
            continue
        if (
            isinstance(parent_params, dict)
            and name in parent_params
            and callable(parent_get_source)
            and _is_commandline(parent_get_source(name))
        ):
            merged[name] = parent_params[name]
            continue
        merged[name] = value
    return merged


def _wait_session_ready(sock_path: str, timeout: float = 10.0) -> dict:
    """Poll the GDB RPC server until the session reports ``state == ready``.

    Raises ``JLinkManagerError`` on timeout (including the last state/error
    observed) so callers can roll the whole start transaction back.
    """
    deadline = time.monotonic() + timeout
    last_state = None
    last_error = None

    while True:
        client = GDBClient(str(sock_path))
        try:
            result = client.call("status", timeout=5.0)
            state = result.get("state")
            if state == "ready":
                return result
            if state == "error":
                last_state = state
                last_error = result.get("error_reason") or last_error
                raise JLinkManagerError(
                    t(
                        "cli.jlink.session_not_ready",
                        state=last_state,
                        error=last_error or "none",
                    )
                )
            last_state = state
        except JLinkManagerError:
            raise
        except GDBClientError as exc:
            last_error = str(exc)
        finally:
            client.close()

        if time.monotonic() >= deadline:
            raise JLinkManagerError(
                t(
                    "cli.jlink.session_not_ready",
                    state=last_state or "unknown",
                    error=last_error or "none",
                )
            )
        time.sleep(_SESSION_READY_POLL_INTERVAL)


def _wait_gdb_process_exit(session, timeout: float = 5.0) -> None:
    """Wait for a GDB session's process to exit (identity check not needed)."""
    pid = getattr(session, "gdb_pid", None)
    if not pid:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.1)


def _stop_gdb_session(session_id: str) -> None:
    """Gracefully stop a GDB session, falling back to forced cleanup."""
    session = get_session(session_id)
    if session is None:
        return

    if session.sock_path:
        try:
            with GDBClient(str(session.sock_path)) as client:
                client.call("stop", before_detach="")
        except GDBClientError:
            # Server unresponsive: force cleanup below.
            pass
        else:
            _wait_gdb_process_exit(session)

    cleanup_session(session_id)


def _stop_associated_session(instance) -> list:
    """Stop the GDB session attached to ``instance`` (best effort).

    Returns a list of cleanup error strings; never raises.
    """
    errors = []
    session_id = getattr(instance, "session_id", None)
    if not session_id:
        return errors

    try:
        _stop_gdb_session(session_id)
    except Exception as exc:  # pragma: no cover - defensive
        errors.append(f"session {session_id}: {exc}")

    instance.session_id = None
    try:
        _save_instance(instance)
    except Exception as exc:
        errors.append(f"failed to persist instance {instance.instance_id}: {exc}")
    return errors


def _connect_gdb_session(
    instance,
    *,
    binary: Optional[str],
    gdb_path: str,
    timeout: int,
    session_id: Optional[str] = None,
    init_cmds: Optional[list] = None,
) -> str:
    """Create a GDB session for ``instance`` and wait until it is ready.

    ``session_id`` reuses a previous session id (jlink restart keeps the
    session id stable so callers' references survive a restart).
    ``init_cmds`` are GDB commands executed right after the session is
    ready (e.g. J-Link ``monitor exec`` device configuration).
    """
    gdb_process = launch_target(
        remote=f"127.0.0.1:{instance.port}",
        binary=binary,
        timeout=timeout,
        gdb_path=gdb_path,
        session_id=session_id,
    )
    session = gdb_process.session
    # Record the id immediately so failure cleanup can find the session.
    instance.session_id = session.session_id
    instance.session_config = {
        "binary": binary,
        "gdb_path": gdb_path,
        "timeout": timeout,
        "init_cmds": list(init_cmds or []),
    }

    _wait_session_ready(session.sock_path)
    init_errors = _run_init_cmds(session, instance.session_config["init_cmds"])
    if init_errors:
        instance.init_errors = init_errors
    _save_instance(instance)
    return session.session_id


def _run_init_cmds(session, init_cmds: list) -> list:
    """Execute ``init_cmds`` over the fresh session; return failures.

    Failures are collected (not raised) so a partially applicable init
    command never tears down an otherwise working session; the caller
    decides whether to surface them.
    """
    errors = []
    for command in init_cmds or []:
        try:
            with GDBClient(str(session.sock_path)) as client:
                result = client.call("exec", command=command)
        except GDBClientError as exc:
            errors.append(f"{command}: {exc}")
            continue
        if isinstance(result, dict) and result.get("error"):
            errors.append(f"{command}: {result['error']}")
    return errors


def _cleanup_failed_instance(instance) -> list:
    """Best-effort rollback of a partially started instance.

    Each step is isolated so a cleanup failure can never mask the original
    startup error.
    """
    errors = []

    session_id = getattr(instance, "session_id", None)
    if session_id:
        try:
            _stop_gdb_session(session_id)
        except Exception as exc:
            errors.append(f"session {session_id}: {exc}")

    try:
        result = stop_instance(instance.instance_id)
        if result.get("status") == "stop_failed":
            errors.append(
                f"JLinkGDBServer {instance.instance_id} did not stop"
            )
    except Exception as exc:
        errors.append(f"stop_instance {instance.instance_id}: {exc}")

    return errors


def _resolve_instance_id(instance_id: Optional[str]) -> str:
    """Return the requested id, or the only running one when unambiguous."""
    if instance_id:
        return instance_id

    instances = [instance for instance in list_instances() if instance.running]
    if not instances:
        raise JLinkManagerError(t("cli.jlink.no_instances"))
    if len(instances) > 1:
        ids = ", ".join(instance.instance_id for instance in instances)
        raise JLinkManagerError(
            t("cli.jlink.ambiguous_instance", instances=ids)
        )
    return instances[0].instance_id


@main.group(invoke_without_command=True, help=t("cli.jlink.doc"),
            epilog=t("cli.jlink.epilog"))
@_jlink_start_options
def jlink(
    device: Optional[str],
    select: Optional[str],
    binary: Optional[str],
    gdb_path: str,
    jlink_path: str,
    speed: Optional[str],
    rtos: Optional[str],
    interface: str,
    port: Optional[int],
    timeout: int,
    init_cmds,
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
        rtos=rtos,
        interface=interface,
        port=port,
        timeout=timeout,
        init_cmds=init_cmds,
        extra_args=extra_args,
    )


@jlink.command("start", help=t("cli.jlink.start.doc"), epilog=t("cli.jlink.start_epilog"))
@_jlink_start_options
def jlink_start(
    device: Optional[str],
    select: Optional[str],
    binary: Optional[str],
    gdb_path: str,
    jlink_path: str,
    speed: Optional[str],
    rtos: Optional[str],
    interface: str,
    port: Optional[int],
    timeout: int,
    init_cmds,
    extra_args,
) -> None:
    """Start JLinkGDBServer and connect GDB"""
    ctx = click.get_current_context()
    merged = _merge_group_params(ctx)
    if merged:
        device = merged.get("device", device)
        select = merged.get("select", select)
        binary = merged.get("binary", binary)
        gdb_path = merged.get("gdb_path", gdb_path)
        jlink_path = merged.get("jlink_path", jlink_path)
        speed = merged.get("speed", speed)
        rtos = merged.get("rtos", rtos)
        interface = merged.get("interface", interface)
        port = merged.get("port", port)
        timeout = merged.get("timeout", timeout)
        init_cmds = merged.get("init_cmds", init_cmds)
        extra_args = merged.get("extra_args", extra_args)

    try:
        if not device:
            raise JLinkManagerError(t("cli.jlink.device_required"))
        select = validate_select(select or "")
        _validate_extra_args(list(extra_args or ()))
        if port is None:
            port = find_free_port()
        cmdline = build_gdbserver_cmdline(
            device=device,
            select=select,
            port=port,
            speed=speed,
            rtos=rtos,
            interface=interface,
            extra_args=list(extra_args or ()),
            jlink_exe=jlink_path,
        )
    except JLinkManagerError as e:
        print_error(str(e))
        raise click.exceptions.Exit(1)

    jlink_id = uuid.uuid4().hex[:8]
    log_path = str(JLINK_DIR / f"{jlink_id}.log")
    duplicate_probes = [
        existing for existing in list_instances()
        if existing.running and existing.select == select
    ]

    try:
        instance = start_gdbserver(cmdline, log_path, instance_id=jlink_id)
    except Exception as e:
        print_error(t("cli.jlink.start_failed"), str(e))
        raise click.exceptions.Exit(1)

    try:
        session_id = _connect_gdb_session(
            instance,
            binary=binary,
            gdb_path=gdb_path,
            timeout=timeout,
            init_cmds=list(init_cmds or ()),
        )
    except BaseException as exc:
        # Roll the whole transaction back; cleanup errors must not replace the
        # original failure reason.
        cleanup_errors = _cleanup_failed_instance(instance)
        print_error(
            t("cli.jlink.connect_failed"),
            str(exc) or exc.__class__.__name__,
            cleanup_errors or None,
        )
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise click.exceptions.Exit(1) from exc

    payload = {
        "jlink_id": instance.instance_id,
        "port": instance.port,
        "device": instance.device,
        "select": instance.select,
        "session_id": session_id,
        "status": "started",
    }
    init_errors = getattr(instance, "init_errors", None)
    if init_errors:
        payload["init_errors"] = init_errors
    if duplicate_probes:
        first = duplicate_probes[0]
        payload["warning"] = t(
            "cli.jlink.probe_in_use_warning",
            select=select,
            instance_id=first.instance_id,
            port=first.port,
        )
    print_json(payload)


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

            results = []
            removed_stale = []
            for instance in instances:
                if not instance.running:
                    # Dead record (process gone or PID recycled): drop the
                    # metadata instead of reporting a bogus stop.
                    delete_instance_metadata(instance.instance_id)
                    removed_stale.append(instance.instance_id)
                    continue
                cleanup_errors = _stop_associated_session(instance)
                result = stop_instance(instance.instance_id)
                if cleanup_errors:
                    result["session_cleanup_errors"] = cleanup_errors
                results.append(result)

            failed = [
                result for result in results
                if result.get("status") == "stop_failed"
            ]
            if failed:
                print_error(
                    t("cli.jlink.stop_failed"),
                    json.dumps({"failed": failed, "removed_stale": removed_stale}),
                )
                raise click.exceptions.Exit(1)

            print_json({
                "stopped": results,
                "removed_stale": removed_stale,
                "count": len(results),
                "status": "stopped",
            })
            return

        resolved = _resolve_instance_id(jlink_id)
        instance = get_instance(resolved)
        if instance is None:
            raise JLinkManagerError(
                t("cli.jlink.no_instance", instance_id=resolved)
            )

        cleanup_errors = _stop_associated_session(instance)
        result = stop_instance(resolved)
        if cleanup_errors:
            result["session_cleanup_errors"] = cleanup_errors
        if result.get("status") == "stop_failed":
            print_error(t("cli.jlink.stop_failed"), json.dumps(result))
            raise click.exceptions.Exit(1)
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
        instance = get_instance(resolved)
        if instance is None:
            raise JLinkManagerError(
                t("cli.jlink.no_instance", instance_id=resolved)
            )

        # Keep the session id stable across the restart so callers'
        # references (e.g. $SESSION in scripts) survive.  Capture it
        # before _stop_associated_session clears the field.
        previous_session_id = instance.session_id
        session_cleanup_errors = _stop_associated_session(instance)
        stop_result = stop_instance(resolved)
        if stop_result.get("status") == "stop_failed":
            print_error(t("cli.jlink.stop_failed"), json.dumps(stop_result))
            raise click.exceptions.Exit(1)

        restarted = start_gdbserver(
            instance.cmdline,
            instance.log_path,
            instance_id=instance.instance_id,
        )
    except click.exceptions.Exit:
        raise
    except Exception as e:
        print_error(t("cli.jlink.restart_failed"), str(e))
        raise click.exceptions.Exit(1)

    # Reconnect using the persisted session settings; users who want different
    # settings should stop and start again.  The previous session id is
    # reused so callers do not have to track a new one after a restart.
    config = dict(instance.session_config or {})
    try:
        session_id = _connect_gdb_session(
            restarted,
            binary=config.get("binary"),
            gdb_path=config.get("gdb_path") or "gdb",
            timeout=config.get("timeout", 600),
            session_id=previous_session_id or None,
            init_cmds=config.get("init_cmds") or [],
        )
    except BaseException as exc:
        cleanup_errors = _cleanup_failed_instance(restarted)
        print_error(
            t("cli.jlink.connect_failed"),
            str(exc) or exc.__class__.__name__,
            cleanup_errors or None,
        )
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise click.exceptions.Exit(1) from exc

    payload = {
        "jlink_id": restarted.instance_id,
        "port": restarted.port,
        "device": restarted.device,
        "select": restarted.select,
        "session_id": session_id,
        "status": "restarted",
    }
    if session_cleanup_errors:
        payload["session_cleanup_errors"] = session_cleanup_errors
    init_errors = getattr(restarted, "init_errors", None)
    if init_errors:
        payload["init_errors"] = init_errors
    print_json(payload)


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
        entries.append({
            "jlink_id": instance.instance_id,
            "port": instance.port,
            "device": instance.device,
            "select": instance.select,
            "pid": instance.pid,
            "log_path": instance.log_path,
            "started_at": instance.started_at,
            "running": instance.running,
            "session_id": instance.session_id,
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
