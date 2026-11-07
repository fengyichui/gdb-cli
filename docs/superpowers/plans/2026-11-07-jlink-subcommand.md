# J-Link GDB Server 子命令 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `gdb-cli jlink` 子命令组：自动启动/停止/重启 JLinkGDBServer，并自动建立 GDB 调试会话（失败即返回失败原因）。

**Architecture:** 新增 `src/gdb_cli/jlink.py` 进程管理器（spawn/wait/持久化/身份验证），`cli.py` 增加 `jlink` 命令组。`start` 启动 JLinkGDBServer → 等待端口就绪 → 调用现有 `launch_target` 建立 GDB 会话。实例元数据持久化在 `~/.gdb-cli/jlink/`。

**Tech Stack:** Python 3.8+（click、subprocess、socket、json），复用 `session._read_proc_starttime`。

**Spec:** 本文件（用户口述需求 + 实测验证的事实）。

## 实测事实（实现依据，不可偏离）

- JLinkGDBServer V8.88：`-select usb`（无序号/昵称时多设备会弹 GUI）、`-select ip=HOST:PORT`、`-device` 必填。
- `-nogui` 抑制 DLL 对话框；本项目**始终强制** `-nogui`。
- 固定默认参数：`-if SWD -nolocalhostonly -halt -nosilent -vd -noir -notimeout`（`-if` 可被用户覆盖）。
- `-speed` 不传 = 自动；`-port` 默认 2331，本项目自动分配空闲端口。
- 设备枚举：`echo "ShowEmuList" | JLinkExe -nogui 1`，输出行 `J-Link[N]: Connection: USB, Serial number: X, ProductName: Y, Nickname: Z`。
- 用户明确要求：`-select usb` 时**必须**带 USB 序号或昵称（`-select usb=<sn>` / `usb=<nickname>`），否则报错提示用户用 `jlink devices` 枚举，绝不允许多设备弹 GUI。
- `jlink start` 必须自动建立 GDB 调试会话；失败则输出失败原因并 exit 1。
- `gdb-cli jlink -d DEV ...`（无子命令）等价 `jlink start`。

## Global Constraints

- 不修改 `launcher.py/session.py/handlers.py` 等现有文件的行为（只 import 复用）。
- 新代码注释用英文；用户可见 JSON 输出沿用 `print_json` 风格。
- JLinkGDBServer 可执行文件默认 `JLinkGDBServer`，`--jlink-path` 可指定。
- 端口就绪判定：TCP connect 成功（不只是进程活着）。
- 退出码：成功 0；任何失败 1（沿用 `raise click.exceptions.Exit(1)`）。
- 所有 i18n key 三语言（en/zh_cn/ru）补齐，CLI 帮助不得出现 `[MISSING:...]`。

## Review Focus（易出问题的输入类）

1. `-select usb` 不带序号/昵称 → 必须报错并提示 `jlink devices`，不能启动（防 GUI 弹窗）。
2. `-device` 缺失 → 报错（JLinkGDBServer 必填参数）。
3. 端口被占用 → 自动换空闲端口（用户未显式指定 `-port` 时）；显式指定且被占 → 报错。
4. JLinkGDBServer 启动后连接目标失败（如设备名错）→ 进程会在数秒内退出，start 必须检测到并把日志尾部作为失败原因返回。
5. GDB 会话建立失败（如 gdb-path 错）→ 返回 launch_target 的异常消息，JLinkGDBServer 进程要回收。
6. `stop` 遇 PID 复用 → 复用 `/proc` starttime 身份验证，PID 不匹配时只删元数据不杀进程。
7. `restart` 无先前配置 → 报错提示先 start。

---

### Task 1: `jlink.py` 核心管理器（无 GDB 会话部分）

**Files:**
- Create: `src/gdb_cli/jlink.py`
- Test: `tests/test_jlink.py`

**Interfaces:**
- Consumes: `gdb_cli.session._read_proc_starttime`（身份验证）。
- Produces（Task 2 CLI 依赖，名字精确）:
  - `JLINK_DIR = Path.home() / ".gdb-cli" / "jlink"`
  - `class JLinkManagerError(Exception)` — message 直接面向用户
  - `@dataclass JLinkInstance`: `instance_id: str`, `cmdline: List[str]`, `port: int`, `device: str`, `select: str`, `pid: Optional[int]`, `start_time: Optional[str]` (proc starttime), `log_path: str`, `started_at: float`, `extra: Dict[str, str]`
  - `def build_gdbserver_cmdline(*, device: str, select: str, port: int, speed: Optional[str] = None, interface: str = "SWD", extra_args: List[str]) -> List[str]`
  - `def validate_select(select: str) -> None` — raise `JLinkManagerError` 当 `usb` 不带 `=` 值或格式非法
  - `def find_free_port() -> int`
  - `def start_gdbserver(cmdline, log_path, *, wait_timeout=15.0) -> JLinkInstance` — spawn（`start_new_session=True`，stdout/stderr→log 文件），轮询 TCP connect 到 `127.0.0.1:port` 就绪；进程提前退出则 raise，错误消息含日志尾部最后 15 行
  - `def stop_instance(instance_id: str) -> dict` / `def list_instances() -> List[JLinkInstance]` / `def get_instance(instance_id) -> Optional[JLinkInstance]` / `def restart_instance(instance_id) -> JLinkInstance`
  - `def enumerate_usb_devices(jlink_exe="JLinkExe") -> List[dict]`（解析 ShowEmuList 输出，返回 `[{"index":0,"connection":"USB","serial":"1057723511","nickname":"nRF54L15DK","product":"J-Link OB-..."}]`）
- 持久化：每个实例写 `JLINK_DIR/<id>.json`（`asdict(JLinkInstance)`）；stop/restart 前用 `_read_proc_starttime(pid)` 比对 `start_time`，不匹配只删 json 不发信号（与 session.cleanup_session 相同的防误杀语义）。

**Step 1（测试先行）**：`tests/test_jlink.py` 覆盖：
- `build_gdbserver_cmdline` 输出包含强制参数 `-nogui -if SWD -nolocalhostonly -halt -nosilent -vd -noir -notimeout`、`-device D`、`-select usb=123`、`-port P`；`speed` 传入时含 `-speed S`、不传时无 `-speed`；`interface="JTAG"` 时 `-if JTAG`；`extra_args` 原样追加在末尾。
- `validate_select("usb")` / `validate_select("ip")` raise；`validate_select("usb=123")`、`validate_select("usb=昵称")`、`validate_select("ip=172.25.176.1:19025")` 通过。
- `find_free_port`（monkeypatch socket.bind 到固定端口断言返回值）。
- `start_gdbserver`：mock `subprocess.Popen` + mock TCP 探测（monkeypatch `jlink._port_open` 返回 True）→ 返回实例且 json 落盘；进程 poll() 返回非 None（提前退出）→ raise，消息含 mock 日志尾部。
- `stop_instance`：PID starttime 不匹配 → 不调用 os.kill、json 删除（monkeypatch `jlink._read_proc_starttime` / `os.kill`）；匹配 → kill 被调用。
- `enumerate_usb_devices`：用固定样例输出（含 "J-Link[0]: Connection: USB, Serial number: 1057723511, ProductName: J-Link OB-nRF5340-NordicSemi, Nickname: nRF54L15DK"）monkeypatch subprocess.run 断言解析结果。

**Step 2**：运行 `pytest tests/test_jlink.py -q` 确认全部 FAIL（模块不存在）。

**Step 3**：实现 `src/gdb_cli/jlink.py`。要点：
- TCP 就绪探测 helper `_port_open(host, port) -> bool`（socket.create_connection, timeout 0.5）。
- 就绪轮询间隔 0.2s；每次轮询先 `process.poll()`。
- `restart_instance` = stop（容忍已死）+ 用原 `cmdline` 重新 `start_gdbserver`（同一 json 覆盖）。
- `extra_args` 用于透传其余 JLinkGDBServer 参数（Task 2 收集）。

**Step 4**：`pytest tests/test_jlink.py -q` 全 PASS；`ruff check src/gdb_cli/jlink.py tests/test_jlink.py` 干净。

**Step 5**：`git commit -m "feat(jlink): add JLinkGDBServer process manager"`。

---

### Task 2: `jlink` CLI 命令组 + 自动 GDB 会话

**Files:**
- Modify: `src/gdb_cli/cli.py`（新增 `jlink` group；不改现有命令）
- Modify: `src/gdb_cli/locales/en.py`、`zh_cn.py`、`ru.py`（新增 `cli.jlink.*` keys）
- Test: `tests/test_jlink.py`（追加 CLI 层测试）、`tests/test_cli_async.py`（i18n 完整性测试自动覆盖新 keys）

**Interfaces:**
- Consumes: Task 1 全部；`gdb_cli.launcher.launch_target`（现有签名）；`print_json/print_error`。
- Produces（用户可见命令面）:
  - `gdb-cli jlink [-d/--device] [--select] [-b/--binary] [--gdb-path] [--jlink-path] [--speed] [--if] [--port] [--allow-write] [--allow-call] [--timeout] [--extra-arg X ...] ] [start]`
    - `--select` 必填；格式校验委托 `validate_select`；缺子命令时默认 `start`（实现：group 的 `invoke_without_command=True` + `ctx.invoke(start_cmd)`）。
    - `--extra-arg`（multiple）透传任意 JLinkGDBServer 参数（如 `-rtos`、`-swoport`、`-jlinkscriptfile`），拼进 `extra_args`。
    - 流程：`build_gdbserver_cmdline` → `start_gdbserver` → `launch_target(remote=f"127.0.0.1:{port}", binary=..., gdb_path=..., allow_write/call, timeout)` → 输出 `{"jlink_id","port","device","select","session_id","status":"started"}`。
    - 任何一步失败：`print_error` + Exit(1)；**若 GDBServer 已起而 launch_target 失败，回收该 GDBServer 实例**（调 `stop_instance`）。
  - `gdb-cli jlink stop [-s/--jlink-id ID | --all]`
  - `gdb-cli jlink restart [-s/--jlink-id ID]`（无 ID 且仅一个实例时可用它；多个则报错列出）
  - `gdb-cli jlink status [-s/--jlink-id ID]`（默认全部）
  - `gdb-cli jlink devices`（`enumerate_usb_devices` 输出 JSON）
- `jlink_id` 用 8 位短 id（与 session_id 风格一致，`uuid4()[:8]`）。

**Step 1（测试先行）**：
- `test_cli_async.py` 已有的 t() 键完整性测试会自动覆盖新 locale keys（先写 keys 前跑一次确认会 FAIL——红）。
- `tests/test_jlink.py` 追加：
  - 默认子命令：用 FakeClick（test_cli_async 的模式）调用 `cli.jlink(...)` 无 subcommand → 内部调用了 start 的处理函数（mock `jlink.start_gdbserver` / `cli.launch_target`，断言被调用）。
  - `--select usb` 无值 → 报错消息含 "devices" 提示。
  - launch_target 抛 GDBLauncherError → `stop_instance` 被调用 + Exit(1)。
- locale：三语言各新增约 20 个 `cli.jlink.*` keys（start/stop/restart/status/devices 的 doc + 每个选项 help + 错误消息：select_required、usb_selector_required、device_required、port_busy、no_instance、ambiguous_instance、start_failed、connect_failed）。

**Step 2**：跑测试确认 FAIL。

**Step 3**：实现。要点：
- group 定义：`@main.group(invoke_without_command=True)` + `@click.pass_context`；无 subcommand 且带 `-d` 时 `ctx.invoke(start_cmd)`；无 `-d` 也无子命令 → 打印 help。
- `--select usb=<sn>` 传给 GDBServer 时原样 `-select usb=1057723511`（nickname 同理，SEGGER 支持 `usb=<nickname>`）；`--select ip=HOST:PORT` → `-select ip=HOST:PORT`。
- start 中 `find_free_port()`（用户显式 `--port` 则直接用；启动失败且错误含端口占用时重试一次换端口——可选，保守起见：显式端口被占直接报错）。
- `launch_target` 失败回收：try/except 里 `stop_instance(jlink_id)`，再 `raise`。

**Step 4**：`pytest tests/test_jlink.py tests/test_cli_async.py -q` 全 PASS；`ruff check` 干净；`.venv/bin/gdb-cli jlink --help` 无 `[MISSING:]`。

**Step 5**：`git commit -m "feat(jlink): add jlink command group with auto GDB session"`。

---

### Task 3: 真实硬件端到端验证（不写产品代码）

**Files:** 无新文件；运行命令并记录证据。

**Step 1**：USB 路径全链路：
```bash
.venv/bin/gdb-cli jlink devices                       # 应列出 nRF54L15DK
.venv/bin/gdb-cli jlink -d nRF54L15_M33 --select usb=1057723511
# 期望输出含 session_id 与 status=started
.venv/bin/gdb-cli status --session <id>               # state=ready
.venv/bin/gdb-cli registers --session <id> --names pc,sp,lr
.venv/bin/gdb-cli jlink stop --all
```
**Step 2**：IP 路径：`--select ip=172.25.176.1:19025` 同上（注意该 server 接的是另一块板，device 名需 `jlink` 起服后从 status 确认；若 device 不匹配导致 GDBServer 报错，失败原因应完整呈现——这也是验收点）。
**Step 3**：失败路径验收：错误 device 名（`-d WRONG`）→ start 返回 JLinkGDBServer 日志尾部作为原因，exit 1，无残留进程/端口；`--select usb`（无值）→ 防弹窗错误。
**Step 4**：`pytest tests -q`（全量回归）+ `ruff check src/gdb_cli tests`。
**Step 5**：`git commit -m "test(jlink): e2e verification against nRF54L15DK"`（如有测试补充）。

---

## Self-Review 结论

- 规格覆盖：自动启动/重启/终止/状态/枚举/全参数透传/强制 -nogui/usb 必须带选择器/自动 GDB 会话/默认子命令 start —— 均有任务对应。
- 类型一致性：`JLinkInstance`/`start_gdbserver`/`stop_instance` 等在 Task 1 定义、Task 2 按名消费，已核对。
- Review Focus 7 条均有对应测试步骤。
