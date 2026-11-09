"""
Chinese (Simplified) Catalog - 简体中文翻译目录
"""

# ``jlink --help`` 与 ``jlink start --help`` 共用，保证两处对
# JLinkGDBServer 选项的说明完全一致。
_JLINK_GDBSERVER_EPILOG = (
    "\b\n"
    "gdb-cli 对接的 JLinkGDBServer 选项。每项依次为：服务器选项、作用、\n"
    "对应的 gdb-cli 选项：\n"
    "  -device <name>          选择 J-Link 已知的目标芯片/设备（必填）。\n"
    "                          gdb-cli：-d/--device\n"
    "  -select <sel>           选择调试探针：usb=<序列号|昵称> 或\n"
    "                          ip=HOST:PORT。gdb-cli：--select\n"
    "  -if <interface>         目标接口：SWD、JTAG、FINE 或\n"
    "                          2-wire-JTAG-PIC32。gdb-cli：--if（默认 SWD）\n"
    "  -speed <kHz>            接口时钟频率（kHz）；省略 = 自动检测。\n"
    "                          gdb-cli：--speed（默认自动）\n"
    "  -port <n>               GDB 客户端连接的 TCP 端口；省略 = 由 gdb-cli\n"
    "                          自动选择空闲端口。gdb-cli：--port\n"
    "  -rtos <plugin>          通过 SEGGER 插件启用 RTOS 线程感知。\n"
    "                          gdb-cli：--rtos <名称>，内部自动传入\n"
    "                          -rtos GDBServer/RTOSPlugin_<名称>。\n"
    "                          常用名称：FreeRTOS、embOS、Zephyr、Azure、\n"
    "                          ChibiOS、NuttX。\n"
    "  -swoport <n>            供客户端读取原始 SWO 输出的端口；\n"
    "                          --extra-arg -swoport --extra-arg <n>。\n"
    "  -telnetport <n>         供客户端读取目标 printf 输出的端口；\n"
    "                          --extra-arg -telnetport --extra-arg <n>。\n"
    "  -RTTTelnetPort <n>      SEGGER RTT 输出的 Telnet 端口；\n"
    "                          --extra-arg -RTTTelnetPort --extra-arg <n>。\n"
    "  -x <file>               GDB 命令脚本，仅在第一个 GDB 客户端连接时\n"
    "                          执行一次；--extra-arg -x --extra-arg <file>。\n"
    "  -xc <file>              GDB 命令脚本，每次 GDB 客户端连接时都执行；\n"
    "                          --extra-arg -xc --extra-arg <file>。\n"
    "  -jlinkscriptfile <f>    调试前运行的 J-Link 脚本文件；\n"
    "                          --extra-arg -jlinkscriptfile --extra-arg <f>。\n"
    "  -jtagconf <IR>,<DR>     JTAG 扫描链：总 IR 长度和目标之前的器件数；\n"
    "                          --extra-arg -jtagconf --extra-arg <IR,DR>。\n"
    "  -excdbg <nSteps>        启用异常调试；设置异常返回到断点前需执行的\n"
    "                          指令数；--extra-arg -excdbg --extra-arg <n>。\n"
    "  -powertarget <delay>    延时后给目标上电（1-9；0 表示断电）；\n"
    "                          --extra-arg -powertarget --extra-arg <n>。\n"
    "  -singlerun / -s         只接受一次 GDB 连接，随后退出；\n"
    "                          --extra-arg -singlerun。\n"
    "  -noreset                连接时只暂停 CPU，不复位目标；\n"
    "                          --extra-arg -noreset。\n"
    "  -log <file>             将 GDB Server 通信日志写入 <file>；\n"
    "                          --extra-arg -log --extra-arg <file>。\n"
    "  -settingsfile <file>    从 <file> 加载 J-Link 设置；\n"
    "                          --extra-arg -settingsfile --extra-arg <file>。\n"
    "  -strict                 以严格模式启动 GDB Server；\n"
    "                          --extra-arg -strict。\n"
    "  -endian <little|big>    目标字节序；--extra-arg -endian --extra-arg <e>。\n"
    "\n\b\n"
    "gdb-cli 始终强制注入（不可覆盖）：\n"
    "  -nogui -nolocalhostonly -halt -nosilent -vd -noir -notimeout\n"
    "\n\b\n"
    "保留参数（不可经 --extra-arg 传入，请使用上面的 gdb-cli 选项）：\n"
    "  -device -select -port -if -rtos -gui -nogui\n"
    "\n\b\n"
    "其余 JLinkGDBServer 参数均可通过 --extra-arg 原样传入\n"
    "（每个 --extra-arg 传一个 token）。"
)

ZH_CN_CATALOG = {
    # === CLI Group ===
    "cli.group.help": "GDB CLI for AI - 瘦客户端 CLI + GDB 内置 Python RPC Server",

    # === load command ===
    "cli.load.doc": "加载 core dump，启动 GDB 常驻进程",
    "cli.load.binary_help": "可执行文件路径",
    "cli.load.core_help": "Core dump 文件路径",
    "cli.load.sysroot_help": "sysroot 路径 (跨机器调试)",
    "cli.load.solib_prefix_help": "共享库前缀",
    "cli.load.source_dir_help": "源码目录",
    "cli.load.timeout_help": "心跳超时秒数 (默认 600)",
    "cli.load.gdb_path_help": "GDB 可执行文件路径",

    # === attach command ===
    "cli.attach.doc": "Attach 到运行中进程",
    "cli.attach.pid_help": "目标进程 PID",
    "cli.attach.binary_help": "可执行文件路径 (可选)",
    "cli.attach.scheduler_locking_help": "启用 scheduler-locking",
    "cli.attach.non_stop_help": "启用 non-stop 模式",
    "cli.attach.timeout_help": "心跳超时秒数 (默认 600)",
    "cli.attach.allow_write_help": "允许内存修改",
    "cli.attach.allow_call_help": "允许函数调用",

    # === target command ===
    "cli.target.remote_help": "远程目标地址 (host:port 或 [ipv6]:port)",
    "cli.target.binary_help": "可执行文件路径 (可选)",
    "cli.target.remote_mode_help": "远程连接模式 (remote/extended-remote)",
    "cli.target.scheduler_locking_help": "启用 scheduler-locking",
    "cli.target.non_stop_help": "启用 non-stop 模式",
    "cli.target.timeout_help": "心跳超时秒数 (默认 600)",
    "cli.target.allow_write_help": "允许内存修改",
    "cli.target.allow_call_help": "允许函数调用",

    # === eval-cmd command ===
    "cli.eval_cmd.doc": "求值 C/C++ 表达式",
    "cli.eval_cmd.session_help": "会话 ID",
    "cli.eval_cmd.max_depth_help": "递归深度限制",
    "cli.eval_cmd.max_elements_help": "数组元素限制",
    "cli.eval_cmd.deref_help": "自动解引用指针值",

    # === threads command ===
    "cli.threads.doc": "列出线程",
    "cli.threads.session_help": "会话 ID",
    "cli.threads.range_help": "线程范围 (如 3-10)",
    "cli.threads.limit_help": "最大返回数量",
    "cli.threads.filter_state_help": "过滤状态 (running/stopped)",

    # === bt command ===
    "cli.bt.doc": "获取 backtrace",
    "cli.bt.session_help": "会话 ID",
    "cli.bt.thread_help": "指定线程 ID",
    "cli.bt.limit_help": "最大帧数",
    "cli.bt.full_help": "包含局部变量",
    "cli.bt.range_help": "帧范围 (如 5-15)",

    # === frame command ===
    "cli.frame.doc": "选择栈帧",
    "cli.frame.session_help": "会话 ID",

    # === locals-cmd command ===
    "cli.locals_cmd.doc": "获取局部变量",
    "cli.locals_cmd.session_help": "会话 ID",
    "cli.locals_cmd.thread_help": "线程 ID",
    "cli.locals_cmd.frame_help": "栈帧编号",

    # === exec command ===
    "cli.exec.doc": "执行原始 GDB 命令",
    "cli.exec.session_help": "会话 ID",
    "cli.exec.safety_level_help": "安全级别 (readonly/readwrite/full)",

    # === stop command ===
    "cli.stop.doc": "停止会话，安全退出 GDB",
    "cli.stop.session_help": "会话 ID",
    "cli.stop.before_detach_help": (
        "detach 前执行的 GDB 命令，可多行分隔"
        "（例如 'monitor go' 让目标继续运行）"
    ),
    "cli.stop.force_help": "RPC 停止失败时强制杀死 GDB 进程",
    "cli.stop.cleanup_failed": "清理会话失败: {session_id}",

    # === sessions command ===
    "cli.sessions.doc": "列出所有活跃会话",

    # === status command ===
    "cli.status.doc": "查看会话状态",
    "cli.status.session_help": "会话 ID",

    # === eval-element command ===
    "cli.eval_element.doc": "访问数组/容器中的特定元素",
    "cli.eval_element.session_help": "会话 ID",
    "cli.eval_element.index_help": "元素索引",
    "cli.eval_element.max_depth_help": "递归深度限制",

    # === thread-apply command ===
    "cli.thread_apply.doc": "批量线程操作",
    "cli.thread_apply.session_help": "会话 ID",
    "cli.thread_apply.threads_help": "线程 ID 列表 (如 1,3,5)",
    "cli.thread_apply.all_help": "应用于所有线程",

    # === args command ===
    "cli.args.doc": "获取函数参数",
    "cli.args.session_help": "会话 ID",
    "cli.args.thread_help": "线程 ID",
    "cli.args.frame_help": "栈帧编号",

    # === registers command ===
    "cli.registers.doc": "查看寄存器值",
    "cli.registers.session_help": "会话 ID",
    "cli.registers.names_help": "寄存器名列表，逗号分隔 (如 rax,rbx,rip)",
    "cli.registers.thread_help": "线程 ID",
    "cli.registers.frame_help": "栈帧编号",

    # === memory command ===
    "cli.memory.doc": "检查内存内容",
    "cli.memory.session_help": "会话 ID",
    "cli.memory.size_help": "读取字节数 (默认 64, 最大 4096)",
    "cli.memory.fmt_help": "输出格式 (hex/bytes/string)",

    # === ptype command ===
    "cli.ptype.doc": "查看表达式的类型信息",
    "cli.ptype.session_help": "会话 ID",

    # === thread-switch command ===
    "cli.thread_switch.doc": "切换当前线程",
    "cli.thread_switch.session_help": "会话 ID",

    # === up command ===
    "cli.up.doc": "向调用者方向移动栈帧",
    "cli.up.session_help": "会话 ID",

    # === down command ===
    "cli.down.doc": "向被调用者方向移动栈帧",
    "cli.down.session_help": "会话 ID",

    # === sharedlibs command ===
    "cli.sharedlibs.doc": "查看加载的共享库",
    "cli.sharedlibs.session_help": "会话 ID",

    # === disasm command ===
    "cli.disasm.doc": "反汇编",
    "cli.disasm.session_help": "会话 ID",
    "cli.disasm.start_help": "起始地址或函数名 (默认当前 PC)",
    "cli.disasm.count_help": "指令数量 (默认 20)",
    "cli.disasm.thread_help": "线程 ID",
    "cli.disasm.frame_help": "栈帧编号",

    # === env-check command ===
    "cli.env_check.doc": "环境自检：gdb版本、ptrace权限、Python版本",

    # === jlink command group ===
    "cli.jlink.doc": "管理 JLinkGDBServer 并自动建立 GDB 会话",
    "cli.jlink.epilog": _JLINK_GDBSERVER_EPILOG,
    "cli.jlink.start.doc": "启动 JLinkGDBServer 并连接 GDB",
    "cli.jlink.start_epilog": _JLINK_GDBSERVER_EPILOG,
    "cli.jlink.stop.doc": "停止 JLinkGDBServer 实例",
    "cli.jlink.restart.doc": "重启 JLinkGDBServer 实例（复用已保存的 GDB 会话设置）",
    "cli.jlink.status.doc": "查看 JLinkGDBServer 实例状态",
    "cli.jlink.devices.doc": "列出已连接的 J-Link 调试器",
    "cli.safe_help": (
        "启用安全过滤（readonly 会话：拦截写入、monitor 命令、函数调用；"
        "默认关闭——会话默认拥有完全权限，需要时显式传 --safe）"
    ),
    "cli.jlink.device_help": "目标设备名（如 nRF54L15_M33）",
    "cli.jlink.select_help": "调试器选择器：usb=<序号|昵称> 或 ip=HOST:PORT",
    "cli.jlink.binary_help": "GDB 会话要加载的可执行文件路径（可选）",
    "cli.jlink.gdb_path_help": "GDB 可执行文件路径",
    "cli.jlink.jlink_path_help": "JLinkGDBServer 可执行文件路径",
    "cli.jlink.speed_help": "接口速度（kHz，默认自动）",
    "cli.jlink.rtos_help": (
        "RTOS 插件名，用于线程感知（如 FreeRTOS）；内部自动添加 "
        "-rtos GDBServer/RTOSPlugin_<名称>"
    ),
    "cli.jlink.interface_help": "调试接口（SWD/JTAG）",
    "cli.jlink.port_help": "GDB Server 端口（默认自动选择空闲端口）",
    "cli.jlink.allow_write_help": "允许内存修改",
    "cli.jlink.allow_call_help": "允许函数调用",
    "cli.jlink.timeout_help": "GDB 心跳超时秒数（默认 600）",
    "cli.jlink.extra_arg_help": "额外透传的 JLinkGDBServer 原始参数（可重复）",
    "cli.jlink.jlink_id_help": "J-Link 实例 ID",
    "cli.jlink.all_help": "对所有实例生效",
    "cli.jlink.select_required": "缺少 --select（请使用 usb=<序号|昵称> 或 ip=HOST:PORT）",
    "cli.jlink.usb_selector_required": (
        "不允许只写 --select usb；请先运行 'gdb-cli jlink devices'，"
        "再使用 usb=<序号> 或 usb=<昵称>"
    ),
    "cli.jlink.ip_selector_required": "--select ip 值非法；请使用 ip=HOST:PORT",
    "cli.jlink.rtos_invalid": (
        "无效的 RTOS 插件名：{value}（请使用 FreeRTOS 这样的纯名称，"
        "不能包含路径、空白或控制字符）"
    ),
    "cli.jlink.device_required": "缺少 --device（JLinkGDBServer 必须指定设备名）",
    "cli.jlink.port_busy": "端口 {port} 已被占用",
    "cli.jlink.no_instance": "未找到 J-Link 实例: {instance_id}",
    "cli.jlink.ambiguous_instance": "存在多个 J-Link 实例，请使用 --jlink-id: {instances}",
    "cli.jlink.start_failed": "JLinkGDBServer 启动失败",
    "cli.jlink.connect_failed": "GDB 会话建立失败",
    "cli.jlink.stop_failed": "停止 J-Link 实例失败",
    "cli.jlink.restart_failed": "重启 J-Link 实例失败",
    "cli.jlink.devices_failed": "J-Link 设备枚举失败: {reason}",
    "cli.jlink.process_exited": "JLinkGDBServer 意外退出。最近日志：\n{tail}",
    "cli.jlink.ready_timeout": "JLinkGDBServer 未在 {timeout} 秒内打开端口 {port}",
    "cli.jlink.no_instances": "没有正在运行的 J-Link 实例",
    "cli.jlink.select_invalid": (
        "无效的 --select 值: {value}"
        "（允许的形式：usb=<序号|昵称> 或 ip=HOST:PORT）"
    ),
    "cli.jlink.extra_arg_protected": (
        "额外参数 {arg} 由 gdb-cli 保留，不能覆盖"
    ),
    "cli.jlink.session_not_ready": (
        "GDB 会话未进入就绪状态（最后状态: {state}，最后错误: {error}）"
    ),
    "cli.jlink.port_invalid": "无效端口: {port}（必须在 1-65535 之间）",

    # === Errors ===
    "errors.session_not_found": "会话未找到: {session_id}",
    "errors.connection_error": "连接错误",
    "errors.variable_not_found.suggestion": "检查变量名是否正确，使用 'info locals' 查看当前作用域的变量",
    "errors.syntax_error.suggestion": "检查表达式语法，确保 C/C++ 表达式格式正确",
    "errors.invalid_thread.suggestion": "使用 'threads' 命令查看可用线程列表",
    "errors.invalid_frame.suggestion": "使用 'bt' 命令查看栈帧列表",
    "errors.memory_access_failed.suggestion": "目标内存区域不可访问，可能是优化导致变量被优化掉",
    "errors.no_debug_info.suggestion": "尝试加载 debuginfo: 'dnf debuginfo-install' 或检查 .debug 文件",
    "errors.process_not_found.suggestion": "检查进程是否存在: 'ps aux | grep <进程名>'",
    "errors.ptrace_denied.suggestion": "运行: 'echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope'",
    "errors.command_blocked.suggestion": "该命令被安全策略阻止，使用 --allow-write 或 --allow-call 参数",
    "errors.command_timeout.suggestion": "命令执行超时，尝试增加 --timeout 参数或简化操作",
    "errors.load_timeout.suggestion": "core 文件加载超时，可能文件过大，尝试增加超时时间",
    "errors.socket_not_found.suggestion": "GDB 会话可能已终止，重新运行 'gdb-cli load' 或 'gdb-cli attach'",
    "errors.connection_refused.suggestion": "GDB RPC Server 未响应，检查 GDB 进程是否正常运行",

    # === Environment Check ===
    "env_check.gdb_not_found.error": "GDB 不在 PATH 中",
    "env_check.gdb_not_found.suggestion": "安装 GDB: 'brew install gdb' (macOS) 或 'yum install gdb' (Linux)",
    "env_check.gdb_below_minimum.error": "GDB 版本 {version} 低于最低要求 {minimum}",
    "env_check.gdb_below_minimum.suggestion": "升级 GDB 到 9.0 或更高版本",
    "env_check.gdb_version_warning": "GDB 版本 {version} 支持，但推荐 {recommended}+",
    "env_check.gdb_recommended_suggestion": "建议升级到 GDB 15+ 以获得与 rockylinux/el9 的最佳兼容性",
    "env_check.ptrace_restricted.warning": "ptrace 受限 (scope=1)。只能 attach 子进程。",
    "env_check.ptrace_heavily_restricted.error": "ptrace 严重受限 (scope={scope})",
    "env_check.ptrace_heavily_restricted.suggestion": "运行: echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope",
    "env_check.ptrace_sysctl_suggestion": "或运行: sysctl kernel.yama.ptrace_scope=0",
    "env_check.ptrace_scope_read_error.warning": "无法读取 ptrace_scope (权限不足)",
    "env_check.debuginfo_not_found.suggestion": "二进制文件已被剥离符号 (无调试信息)",
    "env_check.debuginfo_install_rhel": "RHEL/CentOS: dnf debuginfo-install {package}",
    "env_check.debuginfo_install_ubuntu": "Ubuntu/Debian: apt-get install {package}-dbgsym",
    "env_check.debuginfo_install_fedora": "Fedora: dnf install {package}-debuginfo",
    "env_check.debuginfo_separate_file": "或使用独立的 .debug 文件: add-symbol-file /path/to/{package}.debug",

    # === Runtime messages ===
    "errors.session_no_socket": "会话没有 socket: {session_id}",
    "cli.load.session_reused_message": "该 core 文件已有会话",
    "cli.load.failed": "启动 GDB 失败",
    "cli.attach.session_reused_message": "该 PID 已有会话",
    "cli.attach.failed": "Attach 进程失败",
    "cli.target.invalid_format": "无效的远程格式: {remote}",
    "cli.target.session_reused_message": "该远程目标已有会话",
    "cli.target.failed": "连接目标失败",
    "cli.status.gdb_loading_message": "GDB 进程存活，尚未响应",
    "cli.status.gdb_unresponsive_message": "GDB 进程存活，但已无响应",
    "cli.status.session_dead": "会话已终止",
    "cli.status.gdb_process_dead": "GDB 进程 {pid} 已不存在",
    "cli.thread_apply.require_target": "必须指定 --all 或 --threads",

    # === JSON output hints ===
    "hints.threads_pagination": "使用 'threads --range START-END' 查看特定线程",
    "hints.bt_pagination": "使用 'bt --range START-END' 查看特定栈帧",
    "hints.eval_large_array": "使用 'eval-element' 访问特定数组索引",
}
