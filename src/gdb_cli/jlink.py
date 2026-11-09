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
import tempfile
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .i18n import t
from .session import _read_proc_starttime

JLINK_DIR = Path.home() / ".gdb-cli" / "jlink"

DEFAULT_GDBSERVER_EXE = "JLinkGDBServer"
DEFAULT_ENUM_EXE = "JLinkExe"

_READY_POLL_INTERVAL = 0.2
_TAIL_LINES = 15

# Parameters owned by this module.  Extra user arguments must never be able to
# override them, otherwise the persisted instance metadata would lie.
_PROTECTED_GDBSERVER_ARGS = {
    "-select", "-port", "-device", "-if", "-rtos", "-gui", "-nogui",
}

# Characters that must never appear in a probe selector/host: whitespace and
# ASCII control characters.
_UNSAFE_SELECTOR_RE = re.compile(r"[\s\x00-\x1f\x7f]")
_PORT_RE = re.compile(r"^[0-9]+$")
# RTOS plugin names are plain identifiers; the GDBServer/RTOSPlugin_ prefix
# is added by build_gdbserver_cmdline, never supplied by the user.
_RTOS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_+-]*$")


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
    session_id: Optional[str] = None
    session_config: Dict = field(default_factory=dict)
    # Transient: computed on read, never persisted (see ``_save_instance``).
    running: bool = False


def _new_instance_id() -> str:
    return uuid.uuid4().hex[:8]


def _value_after(args: List[str], option: str) -> Optional[str]:
    try:
        return args[args.index(option) + 1]
    except (ValueError, IndexError):
        return None


def _validate_port(port: int) -> int:
    """Return ``port`` as an int, raising when it is outside 1-65535."""
    try:
        port_number = int(port)
    except (TypeError, ValueError):
        port_number = 0
    if not 1 <= port_number <= 65535:
        raise JLinkManagerError(t("cli.jlink.port_invalid", port=port))
    return port_number


def validate_select(select: str) -> str:
    """Validate and normalize the user supplied ``-select`` value.

    Only a closed set of forms is accepted:

    * ``usb=<selector>`` where ``<selector>`` is non-empty, contains no
      whitespace/control characters and is not ``*``.
    * ``ip=<host>:<port>`` where ``<host>`` is non-empty without whitespace and
      ``<port>`` is an integer in 1-65535.

    A bare ``usb`` or ``ip`` would make JLinkGDBServer fall back to its GUI
    device picker when several probes are attached.  We never allow that.

    Returns the normalized (stripped) selector.
    """
    raw = select or ""
    if "\n" in raw or "\r" in raw:
        raise JLinkManagerError(t("cli.jlink.select_invalid", value=raw))

    value = raw.strip()
    if not value:
        raise JLinkManagerError(t("cli.jlink.select_required"))

    if value == "usb":
        raise JLinkManagerError(t("cli.jlink.usb_selector_required"))
    if value == "ip":
        raise JLinkManagerError(t("cli.jlink.ip_selector_required"))

    if value.startswith("usb="):
        selector = value[len("usb="):]
        if (
            not selector
            or selector == "*"
            or _UNSAFE_SELECTOR_RE.search(selector)
        ):
            raise JLinkManagerError(t("cli.jlink.select_invalid", value=value))
        return value

    if value.startswith("ip="):
        host_port = value[len("ip="):]
        host, sep, port_text = host_port.rpartition(":")
        if not sep or not host or _UNSAFE_SELECTOR_RE.search(host):
            raise JLinkManagerError(t("cli.jlink.select_invalid", value=value))
        if not _PORT_RE.match(port_text):
            raise JLinkManagerError(t("cli.jlink.select_invalid", value=value))
        if not 1 <= int(port_text) <= 65535:
            raise JLinkManagerError(t("cli.jlink.select_invalid", value=value))
        return value

    raise JLinkManagerError(t("cli.jlink.select_invalid", value=value))


def validate_rtos(rtos: str) -> str:
    """Validate a user supplied RTOS plugin name.

    Only a plain plugin name such as ``FreeRTOS`` or ``embOS`` is accepted.
    The ``GDBServer/RTOSPlugin_`` prefix is added by
    :func:`build_gdbserver_cmdline`, so paths, separators, whitespace and
    control characters are rejected here.
    """
    raw = rtos or ""
    if "\n" in raw or "\r" in raw:
        raise JLinkManagerError(t("cli.jlink.rtos_invalid", value=raw))
    value = raw.strip()
    if not value or not _RTOS_NAME_RE.match(value):
        raise JLinkManagerError(t("cli.jlink.rtos_invalid", value=raw))
    return value


def _validate_extra_args(extra_args: List[str]) -> None:
    """Reject extra arguments that would override protected parameters."""
    for token in extra_args or []:
        if token in _PROTECTED_GDBSERVER_ARGS:
            raise JLinkManagerError(
                t("cli.jlink.extra_arg_protected", arg=token)
            )


def build_gdbserver_cmdline(
    *,
    device: str,
    select: str,
    port: int,
    speed: Optional[str] = None,
    interface: str = "SWD",
    rtos: Optional[str] = None,
    extra_args: List[str],
    jlink_exe: str = DEFAULT_GDBSERVER_EXE,
) -> List[str]:
    """Build a JLinkGDBServer command line.

    ``-nogui`` and the fixed defaults are always forced.  ``-speed`` is only
    added when explicitly requested (otherwise SEGGER auto-detects it).
    ``rtos`` is a plain plugin name (``FreeRTOS``); the required
    ``GDBServer/RTOSPlugin_`` prefix is added automatically.
    """
    port_number = _validate_port(port)
    normalized_select = validate_select(select)
    normalized_rtos = validate_rtos(rtos) if rtos else None
    _validate_extra_args(list(extra_args or []))

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
        "-select", normalized_select,
        "-port", str(port_number),
    ]
    if speed:
        cmdline.extend(["-speed", str(speed)])
    if normalized_rtos:
        cmdline.extend([
            "-rtos", f"GDBServer/RTOSPlugin_{normalized_rtos}",
        ])
    if extra_args:
        cmdline.extend(extra_args)
    return cmdline


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
        with open(log_path, encoding="utf-8", errors="replace") as log_file:
            tail = deque(
                (line.rstrip("\n") for line in log_file), maxlen=lines
            )
    except OSError:
        return ""
    return "\n".join(tail)


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
    """Persist instance metadata atomically (temp file + ``os.replace``)."""
    JLINK_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(instance)
    # ``running`` is derived from the live process and must not be persisted.
    data.pop("running", None)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=JLINK_DIR,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        ) as temp_file:
            temp_path = temp_file.name
            json.dump(data, temp_file, indent=2)
        os.replace(temp_path, _instance_path(instance.instance_id))
    except Exception:
        if temp_path is not None:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass
        raise


def delete_instance_metadata(instance_id: str) -> None:
    """Remove the persisted JSON for ``instance_id`` (best effort)."""
    try:
        _instance_path(instance_id).unlink()
    except OSError:
        pass


# Backwards-compatible private alias.
_delete_metadata = delete_instance_metadata


def delete_instance_log(log_path: str) -> None:
    """Remove an instance log file (best effort)."""
    try:
        Path(log_path).unlink()
    except OSError:
        pass


def _is_instance_running(instance: JLinkInstance) -> bool:
    """Return True when the persisted PID still identifies our process."""
    if instance.pid is None or instance.start_time is None:
        return False
    return _read_proc_starttime(instance.pid) == instance.start_time


def get_instance(instance_id: str) -> Optional[JLinkInstance]:
    try:
        raw = _instance_path(instance_id).read_text(encoding="utf-8")
        data = json.loads(raw)
        instance = JLinkInstance(**data)
    except (OSError, ValueError, TypeError):
        return None
    instance.running = _is_instance_running(instance)
    return instance


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
    port_number = _validate_port(port)

    # Re-validate at the spawn boundary: the CLI already did this, but a
    # caller could have built the command line by hand.
    validate_select(_value_after(cmdline, "-select") or "")

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
        # Defensive: make sure no partial metadata survives the failure.
        delete_instance_metadata(instance_id)
        raise JLinkManagerError(
            t("cli.jlink.ready_timeout", port=port_number, timeout=wait_timeout)
        )

    # Close the "port opened then died" window as cheaply as possible.
    if process.poll() is not None:
        log_tail = _tail_log(log_path)
        delete_instance_metadata(instance_id)
        raise JLinkManagerError(
            t("cli.jlink.process_exited", tail=log_tail or "<no log output>")
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
    try:
        _save_instance(instance)
    except Exception:
        # Transactional rollback: never leave a live server without metadata.
        _terminate_process(process)
        delete_instance_metadata(instance_id)
        raise
    return instance


def _terminate_process(
    process, term_timeout: float = 5.0, kill_timeout: float = 1.0
) -> bool:
    """Terminate ``process``, escalating to SIGKILL.

    Returns True when the process is confirmed dead.
    """
    try:
        process.terminate()
    except OSError:
        return process.poll() is not None

    try:
        process.wait(timeout=term_timeout)
        return True
    except subprocess.TimeoutExpired:
        pass
    except OSError:
        pass

    try:
        process.kill()
    except OSError:
        return process.poll() is not None

    try:
        process.wait(timeout=kill_timeout)
        return True
    except (subprocess.TimeoutExpired, OSError):
        return process.poll() is not None


def _identity_matches(instance: JLinkInstance) -> bool:
    if instance.pid is None or instance.start_time is None:
        return False
    return _read_proc_starttime(instance.pid) == instance.start_time


def _stop_result(instance_id: str, pid: Optional[int], killed: bool, status: str) -> dict:
    return {
        "jlink_id": instance_id,
        "pid": pid,
        "killed": killed,
        "status": status,
    }


def stop_instance(instance_id: str) -> dict:
    """Stop one persisted JLinkGDBServer instance.

    The PID is only signalled when ``/proc/<pid>`` still reports the persisted
    starttime.  A recycled PID therefore never receives a signal.

    Returns ``status``: ``stopped`` when the process is confirmed gone,
    ``not_running`` when the persisted process had already exited, and
    ``stop_failed`` when the process survived SIGTERM+SIGKILL (metadata and log
    are kept so the user can retry / inspect).
    """
    instance = get_instance(instance_id)
    if instance is None:
        raise JLinkManagerError(
            t("cli.jlink.no_instance", instance_id=instance_id)
        )

    pid = instance.pid
    if pid is None:
        delete_instance_metadata(instance_id)
        delete_instance_log(instance.log_path)
        return _stop_result(instance_id, None, False, "stopped")

    if not _identity_matches(instance):
        # The original process is already gone (or its PID was reused); it is
        # safe to report it as stopped, but never signal the recycled PID.
        delete_instance_metadata(instance_id)
        delete_instance_log(instance.log_path)
        return _stop_result(instance_id, pid, False, "stopped")

    def _finalize() -> dict:
        delete_instance_metadata(instance_id)
        delete_instance_log(instance.log_path)
        return _stop_result(instance_id, pid, True, "stopped")

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        if not _identity_matches(instance):
            delete_instance_metadata(instance_id)
            return _stop_result(instance_id, pid, False, "stopped")
        return _stop_result(instance_id, pid, False, "stop_failed")

    if _wait_process_exit(pid, timeout=5.0):
        return _finalize()

    # Before escalating, re-verify identity: the original may have exited and
    # its PID may now belong to an unrelated process.
    if not _identity_matches(instance):
        return _finalize()

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass

    if _wait_process_exit(pid, timeout=2.0):
        return _finalize()

    if not _identity_matches(instance):
        return _finalize()

    return _stop_result(instance_id, pid, True, "stop_failed")


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
            input="ShowEmuList\nexit\n",
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
