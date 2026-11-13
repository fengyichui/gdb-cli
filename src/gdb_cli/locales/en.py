"""
English Catalog - 英语翻译目录

Source language for all translations.
"""

# Shared verbatim by ``jlink --help`` and ``jlink start --help`` so both
# command levels document the JLinkGDBServer options identically.
_JLINK_GDBSERVER_EPILOG = (
    "\b\n"
    "JLinkGDBServer options bridged by gdb-cli.  Each entry shows the\n"
    "server option, what it does, and the gdb-cli option that maps to it:\n"
    "  -device <name>          Selects the target MCU/device known to J-Link\n"
    "                          (mandatory).  gdb-cli: -d/--device\n"
    "  -select <sel>           Selects the probe: usb=<serial|nickname> or\n"
    "                          ip=HOST:PORT.  gdb-cli: --select\n"
    "  -if <interface>         Target interface: SWD, JTAG, FINE or\n"
    "                          2-wire-JTAG-PIC32.  gdb-cli: --if (SWD)\n"
    "  -speed <kHz>            Interface clock in kHz; omitted = auto-detect.\n"
    "                          gdb-cli: --speed (default auto)\n"
    "  -port <n>               TCP port GDB clients connect to; omitted =\n"
    "                          gdb-cli picks a free port.  gdb-cli: --port\n"
    "  -rtos <name>            Enables RTOS thread awareness.  gdb-cli:\n"
    "                          --rtos <name>.  Supported: FreeRTOS, embOS,\n"
    "                          Zephyr, Azure, ChibiOS, NuttX.\n"
    "  -swoport <n>            Port for clients consuming raw SWO output;\n"
    "                          --extra-arg -swoport --extra-arg <n>.\n"
    "  -telnetport <n>         Port for clients consuming target printf\n"
    "                          output; --extra-arg -telnetport <n>.\n"
    "  -RTTTelnetPort <n>      Telnet port for SEGGER RTT output;\n"
    "                          --extra-arg -RTTTelnetPort --extra-arg <n>.\n"
    "  -x <file>               GDB command file executed once, when the first\n"
    "                          GDB client connects; --extra-arg -x <file>.\n"
    "  -xc <file>              GDB command file executed on every GDB client\n"
    "                          connection; --extra-arg -xc <file>.\n"
    "  -jlinkscriptfile <f>    J-Link script file run before debugging;\n"
    "                          --extra-arg -jlinkscriptfile --extra-arg <f>.\n"
    "  -jtagconf <IR>,<DR>     JTAG scan chain: total IR length and number of\n"
    "                          devices before the target; --extra-arg ...\n"
    "  -excdbg <nSteps>        Enables exception debugging; sets how many\n"
    "                          instructions run until the exception returns;\n"
    "                          --extra-arg -excdbg --extra-arg <nSteps>.\n"
    "  -powertarget <delay>    Powers the target after the given delay\n"
    "                          (1-9; 0 turns power off); --extra-arg ...\n"
    "  -singlerun / -s         Accepts a single GDB connection, then exits;\n"
    "                          --extra-arg -singlerun.\n"
    "  -noreset                Halts the CPU on connect without resetting the\n"
    "                          target; --extra-arg -noreset.\n"
    "  -log <file>             Writes the GDB Server communication log to\n"
    "                          <file>; --extra-arg -log --extra-arg <file>.\n"
    "  -settingsfile <file>    Loads J-Link settings from <file>;\n"
    "                          --extra-arg -settingsfile --extra-arg <file>.\n"
    "  -strict                 Starts GDB Server in strict mode;\n"
    "                          --extra-arg -strict.\n"
    "  -endian <little|big>    Target endianness; --extra-arg -endian <e>.\n"
    "\n\b\n"
    "Always forced by gdb-cli (cannot be overridden):\n"
    "  -nogui -nolocalhostonly -halt -nosilent -vd -noir -notimeout\n"
    "\n\b\n"
    "Reserved via --extra-arg (use the gdb-cli options above):\n"
    "  -device -select -port -if -rtos -gui -nogui\n"
    "\n\b\n"
    "Any other JLinkGDBServer flag can be passed through --extra-arg\n"
    "(one token per --extra-arg)."
)

ENGLISH_CATALOG = {
    # === CLI Group ===
    "cli.group.help": "GDB CLI for AI - Thin client CLI + GDB built-in Python RPC Server",

    # === load command ===
    "cli.load.doc": "Load core dump and start persistent GDB process",
    "cli.load.binary_help": "Executable file path",
    "cli.load.core_help": "Core dump file path",
    "cli.load.sysroot_help": "sysroot path (for cross-machine debugging)",
    "cli.load.solib_prefix_help": "Shared library prefix",
    "cli.load.source_dir_help": "Source code directory",
    "cli.load.timeout_help": "Heartbeat timeout in seconds (default: 600)",
    "cli.load.gdb_path_help": "GDB executable path",

    # === attach command ===
    "cli.attach.doc": "Attach to running process",
    "cli.attach.pid_help": "Target process PID",
    "cli.attach.binary_help": "Executable file path (optional)",
    "cli.attach.scheduler_locking_help": "Enable scheduler-locking",
    "cli.attach.non_stop_help": "Enable non-stop mode",
    "cli.attach.timeout_help": "Heartbeat timeout in seconds (default: 600)",
    "cli.target.remote_help": "Remote target address (host:port or [ipv6]:port)",
    "cli.target.binary_help": "Executable file path (optional)",
    "cli.target.remote_mode_help": "Remote connection mode (remote/extended-remote)",
    "cli.target.scheduler_locking_help": "Enable scheduler-locking",
    "cli.target.non_stop_help": "Enable non-stop mode",
    "cli.target.timeout_help": "Heartbeat timeout in seconds (default: 600)",
    "cli.eval_cmd.doc": "Evaluate C/C++ expression",
    "cli.eval_cmd.session_help": "Session ID",
    "cli.eval_cmd.max_depth_help": "Recursion depth limit",
    "cli.eval_cmd.max_elements_help": "Array element limit",
    "cli.eval_cmd.deref_help": "Automatically dereference pointer values",

    # === threads command ===
    "cli.threads.doc": "List threads",
    "cli.threads.session_help": "Session ID",
    "cli.threads.range_help": "Thread range (e.g., 3-10)",
    "cli.threads.limit_help": "Maximum return count",
    "cli.threads.filter_state_help": "Filter by state (running/stopped)",

    # === bt command ===
    "cli.bt.doc": "Get backtrace",
    "cli.bt.session_help": "Session ID",
    "cli.bt.thread_help": "Specify thread ID",
    "cli.bt.limit_help": "Maximum frame count",
    "cli.bt.full_help": "Include local variables",
    "cli.bt.range_help": "Frame range (e.g., 5-15)",

    # === frame command ===
    "cli.frame.doc": "Select stack frame",
    "cli.frame.session_help": "Session ID",

    # === locals-cmd command ===
    "cli.locals_cmd.doc": "Get local variables",
    "cli.locals_cmd.session_help": "Session ID",
    "cli.locals_cmd.thread_help": "Thread ID",
    "cli.locals_cmd.frame_help": "Frame number",

    # === exec command ===
    "cli.exec.doc": "Execute raw GDB command",
    "cli.exec.session_help": "Session ID",
    "cli.stop.doc": "Stop session and safely exit GDB",
    "cli.stop.session_help": "Session ID",
    "cli.stop.before_detach_help": (
        "Optional GDB command(s) to run before detaching, "
        "newline-separated (rarely needed; J-Link targets resume "
        "automatically on disconnect)"
    ),
    "cli.stop.force_help": "Force-kill the GDB process if the RPC stop fails",
    "cli.stop.cleanup_failed": "Failed to clean up session: {session_id}",

    # === sessions command ===
    "cli.sessions.doc": "List all active sessions",

    # === status command ===
    "cli.status.doc": "Check session status",
    "cli.status.session_help": "Session ID",
    "cli.wait_stop.doc": (
        "Wait until the target stops (breakpoint hit, signal, interrupt)"
    ),
    "cli.wait_stop.session_help": "Session ID",
    "cli.wait_stop.timeout_help": (
        "Maximum seconds to wait; returns stopped=false on timeout (default: 30)"
    ),

    # === eval-element command ===
    "cli.eval_element.doc": "Access array/container element",
    "cli.eval_element.session_help": "Session ID",
    "cli.eval_element.index_help": "Element index",
    "cli.eval_element.max_depth_help": "Recursion depth limit",

    # === thread-apply command ===
    "cli.thread_apply.doc": "Batch thread operations",
    "cli.thread_apply.session_help": "Session ID",
    "cli.thread_apply.threads_help": "Thread ID list (e.g., 1,3,5)",
    "cli.thread_apply.all_help": "Apply to all threads",

    # === args command ===
    "cli.args.doc": "Get function arguments",
    "cli.args.session_help": "Session ID",
    "cli.args.thread_help": "Thread ID",
    "cli.args.frame_help": "Frame number",

    # === registers command ===
    "cli.registers.doc": "View register values",
    "cli.registers.session_help": "Session ID",
    "cli.registers.names_help": "Register names (comma-separated, e.g., rax,rbx,rip)",
    "cli.registers.thread_help": "Thread ID",
    "cli.registers.frame_help": "Frame number",

    # === memory command ===
    "cli.memory.doc": "Inspect memory content",
    "cli.memory.session_help": "Session ID",
    "cli.memory.size_help": "Bytes to read (default: 64, max: 4096)",
    "cli.memory.fmt_help": "Output format (hex/bytes/string)",

    # === ptype command ===
    "cli.ptype.doc": "View type information for expression",
    "cli.ptype.session_help": "Session ID",

    # === thread-switch command ===
    "cli.thread_switch.doc": "Switch current thread",
    "cli.thread_switch.session_help": "Session ID",

    # === up command ===
    "cli.up.doc": "Move toward caller in stack",
    "cli.up.session_help": "Session ID",

    # === down command ===
    "cli.down.doc": "Move toward callee in stack",
    "cli.down.session_help": "Session ID",

    # === sharedlibs command ===
    "cli.sharedlibs.doc": "View loaded shared libraries",
    "cli.sharedlibs.session_help": "Session ID",

    # === disasm command ===
    "cli.disasm.doc": "Disassemble",
    "cli.disasm.session_help": "Session ID",
    "cli.disasm.start_help": "Start address or function name (default: current PC)",
    "cli.disasm.count_help": "Instruction count (default: 20)",
    "cli.disasm.thread_help": "Thread ID",
    "cli.disasm.frame_help": "Frame number",

    # === env-check command ===
    "cli.env_check.doc": "Environment check: GDB version, ptrace permissions, Python version",

    # === jlink command group ===
    "cli.jlink.doc": "Manage JLinkGDBServer and automatically start a GDB session",
    "cli.jlink.epilog": _JLINK_GDBSERVER_EPILOG,
    "cli.jlink.start.doc": "Start JLinkGDBServer and connect GDB",
    "cli.jlink.start_epilog": _JLINK_GDBSERVER_EPILOG,
    "cli.jlink.stop.doc": "Stop JLinkGDBServer instance(s)",
    "cli.jlink.restart.doc": "Restart a JLinkGDBServer instance (reuses persisted GDB session settings)",
    "cli.jlink.status.doc": "Show JLinkGDBServer instance status",
    "cli.jlink.devices.doc": "List attached J-Link probes",
    "cli.jlink.device_help": "Target device name (e.g. nRF54L15_M33)",
    "cli.jlink.select_help": "Probe selector: usb=<serial|nickname> or ip=HOST:PORT",
    "cli.jlink.binary_help": "Executable file path for the GDB session (optional)",
    "cli.jlink.gdb_path_help": "GDB executable path",
    "cli.jlink.jlink_path_help": "JLinkGDBServer executable path",
    "cli.jlink.speed_help": "Interface speed in kHz (default: auto)",
    "cli.jlink.rtos_help": (
        "RTOS for thread awareness: FreeRTOS, embOS, Zephyr, Azure, "
        "ChibiOS or NuttX"
    ),
    "cli.jlink.interface_help": "Debug interface (SWD/JTAG)",
    "cli.jlink.port_help": "GDB server port (default: auto-selected free port)",
    "cli.jlink.timeout_help": "GDB heartbeat timeout in seconds (default: 600)",
    "cli.jlink.init_cmd_help": (
        "GDB command to run once after the session is ready (repeatable, "
        "e.g. 'monitor exec EnableLowPowerHandlingMode')"
    ),
    "cli.jlink.extra_arg_help": "Extra raw JLinkGDBServer argument (repeatable)",
    "cli.jlink.jlink_id_help": "J-Link instance ID",
    "cli.jlink.all_help": "Apply to all instances",
    "cli.jlink.select_required": "Missing --select (use usb=<serial|nickname> or ip=HOST:PORT)",
    "cli.jlink.usb_selector_required": (
        "Bare --select usb is not allowed; run 'gdb-cli jlink devices' "
        "and use usb=<serial> or usb=<nickname>"
    ),
    "cli.jlink.ip_selector_required": "Invalid --select ip value; use ip=HOST:PORT",
    "cli.jlink.rtos_invalid": (
        "Invalid RTOS plugin name: {value} (use a plain name such as "
        "FreeRTOS; no paths, whitespace or control characters)"
    ),
    "cli.jlink.device_required": "Missing --device (JLinkGDBServer requires a device name)",
    "cli.jlink.port_busy": "Port {port} is already in use",
    "cli.jlink.session_reused_message": (
        "A session for this probe already exists; reusing it"
    ),
    "cli.jlink.session_reconnected_message": (
        "The J-Link server is running but its session was gone; reconnected"
    ),
    "cli.jlink.probe_device_conflict": (
        "Probe {select} is already serving device {existing_device} "
        "(instance {instance_id}); stop it before starting device {device}"
    ),
    "cli.jlink.no_instance": "J-Link instance not found: {instance_id}",
    "cli.jlink.ambiguous_instance": (
        "Multiple J-Link instances are running; use --jlink-id: {instances}"
    ),
    "cli.jlink.start_failed": "Failed to start JLinkGDBServer",
    "cli.jlink.connect_failed": "Failed to establish the GDB session",
    "cli.jlink.stop_failed": "Failed to stop J-Link instance",
    "cli.jlink.restart_failed": "Failed to restart J-Link instance",
    "cli.jlink.devices_failed": "Failed to enumerate J-Link devices: {reason}",
    "cli.jlink.process_exited": "JLinkGDBServer exited unexpectedly. Last log lines:\n{tail}",
    "cli.jlink.ready_timeout": (
        "JLinkGDBServer did not open port {port} within {timeout} seconds"
    ),
    "cli.jlink.no_instances": "No J-Link instances are running",
    "cli.jlink.select_invalid": (
        "Invalid --select value: {value} "
        "(accepted forms: usb=<serial|nickname> or ip=HOST:PORT)"
    ),
    "cli.jlink.extra_arg_protected": (
        "Extra argument {arg} is reserved by gdb-cli and cannot be overridden"
    ),
    "cli.jlink.session_not_ready": (
        "GDB session did not become ready "
        "(last state: {state}, last error: {error})"
    ),
    "cli.jlink.port_invalid": "Invalid port: {port} (must be 1-65535)",

    # === Errors ===
    "errors.session_not_found": "Session not found: {session_id}",
    "errors.connection_error": "Connection error",
    "errors.variable_not_found.suggestion": "Check if variable name is correct, use 'info locals' to see variables in current scope",
    "errors.syntax_error.suggestion": "Check expression syntax, ensure C/C++ format is correct",
    "errors.invalid_thread.suggestion": "Use 'threads' command to see available thread list",
    "errors.invalid_frame.suggestion": "Use 'bt' command to see frame list",
    "errors.memory_access_failed.suggestion": "Target memory region is not accessible, variable may be optimized out",
    "errors.no_debug_info.suggestion": "Try loading debuginfo: 'dnf debuginfo-install' or check .debug file",
    "errors.process_not_found.suggestion": "Check if process exists: 'ps aux | grep <process_name>'",
    "errors.ptrace_denied.suggestion": "Run: 'echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope'",
    "errors.command_timeout.suggestion": "Command timed out, try increasing --timeout or simplifying operation",
    "errors.load_timeout.suggestion": "Core file load timed out, file may be too large, try increasing timeout",
    "errors.socket_not_found.suggestion": "GDB session may have terminated, re-run 'gdb-cli load' or 'gdb-cli attach'",
    "errors.connection_refused.suggestion": "GDB RPC Server not responding, check if GDB process is running",

    # === Environment Check ===
    "env_check.gdb_not_found.error": "GDB not found in PATH",
    "env_check.gdb_not_found.suggestion": "Install GDB: 'brew install gdb' (macOS) or 'yum install gdb' (Linux)",
    "env_check.gdb_below_minimum.error": "GDB version {version} is below minimum {minimum}",
    "env_check.gdb_below_minimum.suggestion": "Upgrade GDB to version 9.0 or later",
    "env_check.gdb_version_warning": "GDB version {version} is supported but {recommended}+ is recommended",
    "env_check.gdb_recommended_suggestion": "Consider upgrading to GDB 15+ for best compatibility with rockylinux/el9",
    "env_check.ptrace_restricted.warning": "ptrace is restricted (scope=1). Can only attach to child processes.",
    "env_check.ptrace_heavily_restricted.error": "ptrace is heavily restricted (scope={scope})",
    "env_check.ptrace_heavily_restricted.suggestion": "Run: echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope",
    "env_check.ptrace_sysctl_suggestion": "Or run: sysctl kernel.yama.ptrace_scope=0",
    "env_check.ptrace_scope_read_error.warning": "Cannot read ptrace_scope (permission denied)",
    "env_check.debuginfo_not_found.suggestion": "Binary appears to be stripped (no debug info)",
    "env_check.debuginfo_install_rhel": "RHEL/CentOS: dnf debuginfo-install {package}",
    "env_check.debuginfo_install_ubuntu": "Ubuntu/Debian: apt-get install {package}-dbgsym",
    "env_check.debuginfo_install_fedora": "Fedora: dnf install {package}-debuginfo",
    "env_check.debuginfo_separate_file": "Or use separate .debug file: add-symbol-file /path/to/{package}.debug",

    # === Runtime messages ===
    "errors.session_no_socket": "Session has no socket: {session_id}",
    "cli.load.session_reused_message": "Session already exists for this core file",
    "cli.load.failed": "Failed to start GDB",
    "cli.attach.session_reused_message": "Session already exists for this PID",
    "cli.attach.failed": "Failed to attach to process",
    "cli.target.invalid_format": "Invalid remote format: {remote}",
    "cli.target.session_reused_message": "Session already exists for this remote",
    "cli.target.failed": "Failed to connect to target",
    "cli.status.gdb_loading_message": "GDB process alive, not yet responding",
    "cli.status.gdb_unresponsive_message": "GDB process alive but no longer responding",
    "cli.status.session_dead": "Session dead",
    "cli.status.gdb_process_dead": "GDB process {pid} no longer exists",
    "cli.thread_apply.require_target": "Must specify --all or --threads",

    # === JSON output hints ===
    "hints.threads_pagination": "use 'threads --range START-END' for specific threads",
    "hints.bt_pagination": "use 'bt --range START-END' for specific frames",
    "hints.eval_large_array": "use 'eval-element' to access specific array indices",
}
