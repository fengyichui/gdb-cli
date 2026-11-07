"""J-Link GDB Server process manager.

This module owns everything related to spawning, tracking and stopping a
``JLinkGDBServer`` process.  It deliberately does not know about GDB debug
sessions; the CLI layer wires the GDB session on top of it.
"""

import json
import os
import re
import signal
import socket
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .i18n import t
from .session import _read_proc_starttime

JLINK_DIR = Path.home() / ".gdb-cli" / "jlink"

DEFAULT_GDBSERVER_EXE = "JLinkGDBServer"
DEFAULT_ENUM_EXE = "JLinkExe"

_READY_POLL_INTERVAL = 0.2
_TAIL_LINES = 15


class JLinkManagerError(Exception):
    """Raised for user-facing J-Link manager failures."""


@dataclass
class JLinkInstance:
    """Persisted metadata for one running JLinkGDBServer process."""

    instance_id: str
    cmdline: List[str]
    port: int
    device: str
    select: str
    pid: Optional[int]
    start_time: Optional[str]
    log_path: str
    started_at: float
    extra: Dict[str, str]


def _new_instance_id() -> str:
    return uuid.uuid4().hex[:8]


def _value_after(args: List[str], option: str) -> Optional[str]:
    try:
        return args[args.index(option) + 1]
    except (ValueError, IndexError):
        return None


def build_gdbserver_cmdline(
    *,
    device: str,
    select: str,
    port: int,
    speed: Optional[str] = None,
    interface: str = "SWD",
    extra_args: List[str],
    jlink_exe: str = DEFAULT_GDBSERVER_EXE,
) -> List[str]:
    """Build a JLinkGDBServer command line.

    ``-nogui`` and the fixed defaults are always forced.  ``-speed`` is only
    added when explicitly requested (otherwise SEGGER auto-detects it).
    """
    cmdline = [
        jlink_exe,
        "-nogui",
        "-if", interface,
        "-nolocalhostonly",
        "-halt",
        "-nosilent",
        "-vd",
        "-noir",
        "-notimeout",
        "-device", device,
        "-select", select,
        "-port", str(port),
    ]
    if speed:
        cmdline.extend(["-speed", str(speed)])
    if extra_args:
        cmdline.extend(extra_args)
    return cmdline


def validate_select(select: str) -> None:
    """Validate the user supplied ``-select`` value.

    A bare ``usb`` or ``ip`` would make JLinkGDBServer fall back to its GUI
    device picker when several probes are attached.  We never allow that.
    """
    if not select:
        raise JLinkManagerError(t("cli.jlink.select_required"))

    if select == "usb" or select.startswith("usb="):
        if select.startswith("usb=") and len(select) > len("usb="):
            return
        raise JLinkManagerError(t("cli.jlink.usb_selector_required"))

    if select == "ip" or select.startswith("ip="):
        value = select[len("ip="):] if select.startswith("ip=") else ""
        if value and ":" in value:
            return
        raise JLinkManagerError(t("cli.jlink.ip_selector_required"))


def find_free_port() -> int:
    """Return a currently free TCP port on the loopback interface."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _tail_log(log_path: str, lines: int = _TAIL_LINES) -> str:
    try:
        content = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(content.splitlines()[-lines:])


def _wait_process_exit(pid: int, timeout: float = 5.0) -> bool:
    """Return True as soon as ``pid`` no longer exists."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.1)
    return False


def _instance_path(instance_id: str) -> Path:
    return JLINK_DIR / f"{instance_id}.json"


def _save_instance(instance: JLinkInstance) -> None:
    JLINK_DIR.mkdir(parents=True, exist_ok=True)
    _instance_path(instance.instance_id).write_text(
        json.dumps(asdict(instance), indent=2), encoding="utf-8"
    )


def _delete_metadata(instance_id: str) -> None:
    try:
        _instance_path(instance_id).unlink()
    except OSError:
        pass


def get_instance(instance_id: str) -> Optional[JLinkInstance]:
    try:
        raw = _instance_path(instance_id).read_text(encoding="utf-8")
        data = json.loads(raw)
        return JLinkInstance(**data)
    except (OSError, ValueError, TypeError):
        return None


def list_instances() -> List[JLinkInstance]:
    try:
        paths = sorted(JLINK_DIR.glob("*.json"))
    except OSError:
        return []

    instances = []
    for path in paths:
        instance = get_instance(path.stem)
        if instance is not None:
            instances.append(instance)
    return instances


def start_gdbserver(
    cmdline: List[str],
    log_path: str,
    *,
    wait_timeout: float = 15.0,
    instance_id: Optional[str] = None,
) -> JLinkInstance:
    """Spawn JLinkGDBServer and wait until its GDB port accepts connections."""
    port = _value_after(cmdline, "-port")
    if port is None:
        raise JLinkManagerError("JLinkGDBServer command line is missing -port")
    port_number = int(port)

    # Probe before spawning so an explicitly requested busy port fails with a
    # clear message instead of an opaque server crash.
    if _port_open("127.0.0.1", port_number):
        raise JLinkManagerError(t("cli.jlink.port_busy", port=port_number))

    if instance_id is None:
        instance_id = _new_instance_id()

    log_file_path = Path(log_path)
    if log_file_path.parent:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "ab") as log_file:
        process = subprocess.Popen(
            cmdline,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    deadline = time.monotonic() + wait_timeout
    ready = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_tail = _tail_log(log_path)
            raise JLinkManagerError(
                t("cli.jlink.process_exited", tail=log_tail or "<no log output>")
            )
        if _port_open("127.0.0.1", port_number):
            ready = True
            break
        time.sleep(_READY_POLL_INTERVAL)

    if not ready:
        _terminate_process(process)
        raise JLinkManagerError(
            t("cli.jlink.ready_timeout", port=port_number, timeout=wait_timeout)
        )

    instance = JLinkInstance(
        instance_id=instance_id,
        cmdline=list(cmdline),
        port=port_number,
        device=_value_after(cmdline, "-device") or "",
        select=_value_after(cmdline, "-select") or "",
        pid=process.pid,
        start_time=_read_proc_starttime(process.pid),
        log_path=str(log_path),
        started_at=time.time(),
        extra={},
    )
    _save_instance(instance)
    return instance


def _terminate_process(process) -> None:
    try:
        process.terminate()
    except OSError:
        return
    try:
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def stop_instance(instance_id: str) -> dict:
    """Stop one persisted JLinkGDBServer instance.

    The PID is only signalled when ``/proc/<pid>`` still reports the persisted
    starttime.  A recycled PID therefore never receives a signal; we only drop
    the stale metadata.
    """
    instance = get_instance(instance_id)
    if instance is None:
        raise JLinkManagerError(
            t("cli.jlink.no_instance", instance_id=instance_id)
        )

    pid = instance.pid
    if pid is None:
        _delete_metadata(instance_id)
        return {"jlink_id": instance_id, "pid": None, "killed": False, "status": "stopped"}

    current_start_time = _read_proc_starttime(pid)
    if (
        current_start_time is None
        or instance.start_time is None
        or current_start_time != instance.start_time
    ):
        _delete_metadata(instance_id)
        return {
            "jlink_id": instance_id,
            "pid": pid,
            "killed": False,
            "status": "not_running",
        }

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        _delete_metadata(instance_id)
        return {
            "jlink_id": instance_id,
            "pid": pid,
            "killed": False,
            "status": "not_running",
        }

    if not _wait_process_exit(pid, timeout=5.0):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        _wait_process_exit(pid, timeout=2.0)

    _delete_metadata(instance_id)
    return {"jlink_id": instance_id, "pid": pid, "killed": True, "status": "stopped"}


def restart_instance(instance_id: str) -> JLinkInstance:
    """Stop and re-spawn an instance, reusing its id, cmdline and log path."""
    instance = get_instance(instance_id)
    if instance is None:
        raise JLinkManagerError(
            t("cli.jlink.no_instance", instance_id=instance_id)
        )

    try:
        stop_instance(instance_id)
    except JLinkManagerError:
        # A dead process is fine; we are about to replace it anyway.
        pass

    return start_gdbserver(
        instance.cmdline,
        instance.log_path,
        instance_id=instance.instance_id,
    )


_EMULATOR_LINE_RE = re.compile(
    r"J-Link\[(\d+)\]:\s*Connection:\s*([^,]+),\s*Serial number:\s*([^,]+),"
    r"\s*ProductName:\s*([^,]+),\s*Nickname:\s*(.*)$"
)


def enumerate_usb_devices(jlink_exe: str = DEFAULT_ENUM_EXE) -> List[dict]:
    """Enumerate attached J-Link probes via JLinkExe's ``ShowEmuList``."""
    try:
        completed = subprocess.run(
            [jlink_exe, "-nogui", "1"],
            input="ShowEmuList\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise JLinkManagerError(
            t("cli.jlink.devices_failed", reason=str(exc))
        )

    if completed.returncode != 0:
        raise JLinkManagerError(
            t("cli.jlink.devices_failed", reason=completed.stdout or "")
        )

    devices = []
    for line in completed.stdout.splitlines():
        match = _EMULATOR_LINE_RE.search(line)
        if match is None:
            continue
        devices.append({
            "index": int(match.group(1)),
            "connection": match.group(2).strip(),
            "serial": match.group(3).strip(),
            "product": match.group(4).strip(),
            "nickname": match.group(5).strip(),
        })
    return devices
