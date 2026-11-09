"""
English Catalog - 英语翻译目录

Source language for all translations.
"""

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
    "cli.attach.allow_write_help": "Allow memory modification",
    "cli.attach.allow_call_help": "Allow function calls",

    # === target command ===
    "cli.target.remote_help": "Remote target address (host:port or [ipv6]:port)",
    "cli.target.binary_help": "Executable file path (optional)",
    "cli.target.remote_mode_help": "Remote connection mode (remote/extended-remote)",
    "cli.target.scheduler_locking_help": "Enable scheduler-locking",
    "cli.target.non_stop_help": "Enable non-stop mode",
    "cli.target.timeout_help": "Heartbeat timeout in seconds (default: 600)",
    "cli.target.allow_write_help": "Allow memory modification",
    "cli.target.allow_call_help": "Allow function calls",

    # === eval-cmd command ===
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
    "cli.exec.safety_level_help": "Safety level (readonly/readwrite/full)",

    # === stop command ===
    "cli.stop.doc": "Stop session and safely exit GDB",
    "cli.stop.session_help": "Session ID",
    "cli.stop.before_detach_help": (
        "GDB command(s) to run before detaching, newline-separated "
        "(e.g. 'monitor go' to leave the target running)"
    ),
    "cli.stop.force_help": "Force-kill the GDB process if the RPC stop fails",
    "cli.stop.cleanup_failed": "Failed to clean up session: {session_id}",

    # === sessions command ===
    "cli.sessions.doc": "List all active sessions",

    # === status command ===
    "cli.status.doc": "Check session status",
    "cli.status.session_help": "Session ID",

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
    "cli.jlink.epilog": (
        "\b\n"
        "JLinkGDBServer arguments are mapped to gdb-cli options:\n"
        "  -device DEV             -> -d, --device DEV\n"
        "  -select SELECT          -> --select usb=<serial|nickname> | ip=HOST:PORT\n"
        "  -if IF                  -> --if SWD|JTAG\n"
        "  -speed SPEED            -> --speed kHz (omit = auto)\n"
        "  -port PORT              -> --port (omit = free port auto-picked)\n"
        "  -swoport/-telnetport/   -> --extra-arg\n"
        "  -RTTTelnetPort\n"
        "  -rtos PLUGIN            -> --extra-arg -rtos\n"
        "                            --extra-arg GDBServer/RTOSPlugin_<name>\n"
        "  -x/-xc FILE             -> --extra-arg -x --extra-arg <gdbinit>\n"
        "  -jlinkscriptfile FILE   -> --extra-arg\n"
        "  -jtagconf/-excdbg/      -> --extra-arg\n"
        "  -powertarget\n"
        "  -USB <sn> / -IP <host>  -> use --select instead\n"
        "  -singlerun/-noreset/    -> --extra-arg\n"
        "  -log/-settingsfile\n"
        "\n"
        "Always forced by gdb-cli (cannot be overridden):\n"
        "  -nogui -nolocalhostonly -halt -nosilent -vd -noir -notimeout\n"
        "\n"
        "Reserved (cannot be passed via --extra-arg):\n"
        "  -select, -port, -device, -if, -gui, -nogui\n"
        "\n"
        "Run 'gdb-cli jlink start --help' for all options."
    ),
    "cli.jlink.start.doc": "Start JLinkGDBServer and connect GDB",
    "cli.jlink.start_epilog": (
        "\b\n"
        "Bridged JLinkGDBServer command-line options (see also group help):\n"
        "  -device <name>          -d/--device (mandatory; MCU name J-Link\n"
        "                          knows, e.g. nRF54L15_M33)\n"
        "  -select <sel>           --select usb=<serial|nickname> |\n"
        "                          ip=HOST:PORT\n"
        "  -if <SWD|JTAG|FINE|     --if (default SWD)\n"
        "    2-wire-JTAG-PIC32>\n"
        "  -speed <kHz|auto>       --speed (omit = auto-detect)\n"
        "  -port <n>               --port (omit = auto-picked free port)\n"
        "  -swoport <n>            --extra-arg -swoport --extra-arg <n>\n"
        "  -telnetport <n>         --extra-arg -telnetport --extra-arg <n>\n"
        "  -RTTTelnetPort <n>      --extra-arg -RTTTelnetPort --extra-arg <n>\n"
        "  -rtos <plugin>          --extra-arg -rtos --extra-arg <plugin>\n"
        "                          (RTOS thread awareness; on Linux the\n"
        "                          plugin path must include the GDBServer/\n"
        "                          subdirectory, e.g.\n"
        "                          --extra-arg -rtos\n"
        "                          --extra-arg GDBServer/RTOSPlugin_FreeRTOS\n"
        "                          — bare 'FreeRTOS' fails to resolve)\n"
        "                          Available plugins:\n"
        "                          GDBServer/RTOSPlugin_FreeRTOS\n"
        "                          GDBServer/RTOSPlugin_embOS\n"
        "                          GDBServer/RTOSPlugin_Zephyr\n"
        "                          GDBServer/RTOSPlugin_Azure\n"
        "                          GDBServer/RTOSPlugin_ChibiOS\n"
        "                          GDBServer/RTOSPlugin_NuttX\n"
        "  -x <gdbinit>            --extra-arg -x --extra-arg <file>\n"
        "  -xc <gdbinit>           --extra-arg -xc --extra-arg <file>\n"
        "  -jlinkscriptfile <f>    --extra-arg -jlinkscriptfile --extra-arg <f>\n"
        "  -jtagconf <IR>,<DR>     --extra-arg -jtagconf --extra-arg <IR,DR>\n"
        "  -excdbg <nSteps>        --extra-arg -excdbg --extra-arg <n>\n"
        "  -powertarget <delay>    --extra-arg -powertarget --extra-arg <n>\n"
        "  -singlerun / -s         --extra-arg -singlerun\n"
        "  -noreset                --extra-arg -noreset\n"
        "  -log <file>             --extra-arg -log --extra-arg <file>\n"
        "  -settingsfile <file>    --extra-arg -settingsfile --extra-arg <file>\n"
        "  -strict                 --extra-arg -strict\n"
        "  -endian <little|big>    --extra-arg -endian --extra-arg <e>\n"
        "  -JLinkDevicesXMLPath    --extra-arg (deprecated by SEGGER)\n"
        "  -USB <sn> / -IP <h>     use --select usb=<sn> / ip=<h>:<port> instead\n"
        "\n"
        "gdb-cli always forces (cannot be overridden):\n"
        "  -nogui -nolocalhostonly -halt -nosilent -vd -noir -notimeout\n"
        "\n"
        "Reserved via --extra-arg: -select -port -device -if -gui -nogui.\n"
        "\n"
        "Any other JLinkGDBServer flag not listed passes through\n"
        "--extra-arg verbatim (one token per --extra-arg)."
    ),
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
    "cli.jlink.interface_help": "Debug interface (SWD/JTAG)",
    "cli.jlink.port_help": "GDB server port (default: auto-selected free port)",
    "cli.jlink.allow_write_help": "Allow memory modification",
    "cli.jlink.allow_call_help": "Allow function calls",
    "cli.jlink.timeout_help": "GDB heartbeat timeout in seconds (default: 600)",
    "cli.jlink.extra_arg_help": "Extra raw JLinkGDBServer argument (repeatable)",
    "cli.jlink.jlink_id_help": "J-Link instance ID",
    "cli.jlink.all_help": "Apply to all instances",
    "cli.jlink.select_required": "Missing --select (use usb=<serial|nickname> or ip=HOST:PORT)",
    "cli.jlink.usb_selector_required": (
        "Bare --select usb is not allowed; run 'gdb-cli jlink devices' "
        "and use usb=<serial> or usb=<nickname>"
    ),
    "cli.jlink.ip_selector_required": "Invalid --select ip value; use ip=HOST:PORT",
    "cli.jlink.device_required": "Missing --device (JLinkGDBServer requires a device name)",
    "cli.jlink.port_busy": "Port {port} is already in use",
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
    "errors.command_blocked.suggestion": "Command blocked by safety policy, use --allow-write or --allow-call flag",
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
