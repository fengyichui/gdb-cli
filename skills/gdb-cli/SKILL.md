---
name: gdb-cli
description: |
  GDB debugging assistant that combines source code analysis with runtime state.

  Use this skill when the user wants to:
  - Analyze core dumps or crash dumps
  - Debug running processes with GDB attach
  - Debug embedded targets (Cortex-M, ARM, RISC-V) via J-Link probes
  - Investigate crashes, deadlocks, or memory issues
  - Get intelligent debugging assistance with source code context

  Requires: gdb-cli (pip install gdb-cli) and GDB 9.0+ with Python support.
  For embedded J-Link debugging: JLinkGDBServer + a multi-target GDB
  (gdb-multiarch, or the matching vendor cross GDB like arm-none-eabi-gdb)
  with Python support.
---

# GDB Debug Skill

You are an expert debugger. Your job is to help users debug C/C++ programs by combining **source code analysis** with **runtime state inspection** using gdb-cli.

## Core Principle

Debugging requires TWO kinds of information:
1. **Static Code**: Source files, function definitions, data structures
2. **Dynamic State**: Call stacks, variable values, memory layout, thread states

This skill **automatically correlates both** to provide intelligent debugging assistance.

## Prerequisites Check

Before starting, verify the environment:

```bash
# Check if gdb-cli is installed
which gdb-cli || echo "Install: pip install gdb-cli"

# Check GDB Python support
gdb -nx -q -batch -ex "python print('OK')"
```

If gdb-cli is not installed, guide the user: `pip install git+https://github.com/Cerdore/gdb-cli.git`

For embedded J-Link debugging, also check (Step 1 below): JLinkGDBServer on
PATH and a multi-target GDB — the host's `gdb-multiarch` (Debian/Ubuntu) or
a vendor cross GDB (e.g. arm-none-eabi-gdb) — with Python support.

## Workflow

All entry points produce a `session_id`; pick the one matching your target
and continue with Step 2.

### Step 1: Initialize Debug Session

**For an embedded target behind a J-Link probe (Cortex-M/ARM/RISC-V) —
gdb-cli manages the whole chain:**
`gdb-cli jlink` auto-starts JLinkGDBServer, auto-connects the GDB session,
and verifies the session is `ready` before returning. One command replaces
"start server + connect GDB":

```bash
# Enumerate locally attached USB probes (get serial numbers / nicknames)
gdb-cli jlink devices

# USB probe: one command -> GDBServer + GDB session (returns session_id)
gdb-cli jlink -d <device_name> --select usb=<serial_or_nickname> \
    --binary <firmware.elf> \
    --gdb-path /usr/bin/gdb-multiarch

# Remote probe via J-Link Remote Server
gdb-cli jlink -d <device_name> --select ip=<host>:<port> \
    --binary <firmware.elf> \
    --gdb-path /opt/arm-none-eabi-gdb/bin/arm-none-eabi-gdb

# Lifecycle
gdb-cli jlink status                                  # list managed servers (+ session binding)
gdb-cli jlink restart                                 # restart server + reconnect GDB session
gdb-cli jlink stop --all                              # stop GDB session + server, clean up

# RTOS thread awareness (FreeRTOS etc.): use the standard --rtos option
gdb-cli jlink -d <device_name> --select usb=<sn> --binary <fw.elf> \
    --gdb-path /usr/bin/gdb-multiarch \
    --rtos FreeRTOS
```

**Critical rules for `--select`:**
- `usb` MUST carry a selector: `usb=<serial>` or `usb=<nickname>` (from
  `jlink devices`). Bare `usb` or `usb=*` is rejected — with multiple probes
  attached, an unselected start would pop a GUI dialog on the host.
- `ip=<host>:<port>` for remote probes (e.g. `ip=172.25.176.1:19025`).
- `-d/--device` is the target MCU name J-Link knows (e.g. `nRF54L15_M33`,
  `STM32F407VG`). Wrong names fail fast with the GDBServer log tail.
- Always pass `--gdb-path` pointing at a multi-target GDB. Either works:
  the host's `gdb-multiarch` (Debian/Ubuntu package, covers ARM/RISC-V/
  most targets: `--gdb-path /usr/bin/gdb-multiarch`) or the vendor's cross
  GDB (e.g. `arm-none-eabi-gdb`). A plain host `gdb` usually only supports
  the native architecture and will fail on embedded targets.
  `--binary <fw.elf>` loads symbols so function names, types and source
  lines resolve.
- Fixed internal defaults: `-if SWD -nolocalhostonly -halt -nosilent -vd
  -noir -notimeout`, `-nogui` always forced, `-port` auto-picked. Extra
  JLinkGDBServer args pass through `--extra-arg`, but
  `-select/-port/-device/-if/-rtos/-gui/-nogui` are reserved.
- **RTOS thread awareness** (FreeRTOS/embOS/Zephyr/Azure/ChibiOS/NuttX):
  exposes RTOS tasks as GDB threads. Use `--rtos <name>` with one of:
  `FreeRTOS`, `embOS`, `Zephyr`, `Azure`, `ChibiOS`, `NuttX`.
  Requirements
  verified in practice: the ELF with RTOS symbols must be passed via
  `--binary`; tasks appear in `gdb-cli threads` when the scheduler is
  running (run past `vTaskStartScheduler()`). Caveat: the official
  FreeRTOS plugin may not enumerate tasks on TrustZone non-secure
  FreeRTOS ports (ARM_CM33/non_secure) — symptoms: `threads` shows a
  single thread with `Thread 57005` (0xDEAD) even though
  `uxCurrentNumberOfTasks > 1`.
- `jlink stop` stops the GDB session AND the server. Plain
  `gdb-cli stop --session <id>` stops only the GDB session and keeps the
  server listening (useful to reconnect quickly with `gdb-cli target`).
- On success the output contains BOTH `jlink_id` and `session_id`. Any
  failure exits non-zero with the reason (e.g. GDBServer log tail for a bad
  device name) and leaves no orphan processes.

Embedded notes: registers are architecture-aware (`pc/sp/lr/xpsr` on
Cortex-M); `eval` does not auto-dereference pointers by default
(MMIO-safe) — use `eval --deref` to opt in; the J-Link `monitor` commands
(reset/go/halt/regs) are available via
`gdb-cli exec -s $SESSION "monitor reset"` but REQUIRE the
`--allow-write` session level; to leave the target running
when stopping, use `gdb-cli stop -s $SESSION --before-detach "monitor go"`.

**For a target running on a remote host and port (server ALREADY running —
e.g. a JLinkGDBServer you started yourself, or one left listening after a
jlink session was stopped):**
```bash
gdb-cli target --binary <binary_path> --remote <host_name>:<port_number> [--gdb-path <gdb_path>]
```

**For core dump analysis:**
```bash
gdb-cli load --binary <binary_path> --core <core_path> [--gdb-path <gdb_path>]
```

**For live process debugging:**
```bash
gdb-cli attach --pid <pid> [--binary <binary_path>]
```

**Output:** A `session_id` like `"session_id": "a1b2c3"`.

For `load`, the command may return immediately with `"status": "loading"` while GDB is still parsing symbols and the core file. Poll until it becomes ready:

```bash
gdb-cli status -s $SESSION
```

Wait until the response includes `"state": "ready"` before running heavier inspection commands like `bt`, `threads`, or `eval`.

### Step 2: Gather Initial Information

```bash
# Store session ID
SESSION="<session_id>"

# List all threads
gdb-cli threads -s $SESSION

# Get backtrace (with local variables)
gdb-cli bt -s $SESSION --full

# Get registers
gdb-cli registers -s $SESSION
```

### Step 3: Correlate Source Code (CRITICAL)

For each frame in the backtrace:
1. **Extract frame info**: `{file}:{line} in {function}`
2. **Read source context**: Use `Read` tool to get ±20 lines around the crash point
3. **Get local variables**: `gdb-cli locals -s $SESSION --frame <N>`
4. **Analyze**: Correlate code logic with variable values

**Example correlation:**
```
Frame #0: process_data() at src/worker.c:87
Source code shows:
  85: Node* node = get_node(id);
  86: if (node == NULL) return;
  87: node->data = value;  // ← Crash here

Variables show:
  node = 0x0 (NULL)

Analysis: The NULL check on line 86 didn't catch the issue, or node was set after.
```

### Step 4: Deep Investigation

Use additional commands based on findings:

```bash
# Examine variables
gdb-cli eval -s $SESSION "variable_name"
gdb-cli eval -s $SESSION "ptr->field"
gdb-cli ptype -s $SESSION "struct_name"

# Memory inspection
gdb-cli memory -s $SESSION "0x7fffffffe000" --size 64

# Disassembly
gdb-cli disasm -s $SESSION --count 20

# Check all threads (for deadlock analysis)
gdb-cli thread-apply -s $SESSION bt --all

# View shared libraries
gdb-cli sharedlibs -s $SESSION
```

### Step 5: Generate Analysis Report

Structure your findings as:

```markdown
## Debug Session Summary

**Session ID**: `<session_id>`
**Mode**: core dump / attach
**Binary**: `<binary_path>`
**Thread Count**: `<N>`

## Crash Point Analysis

### Frame #0: `<function>` at `<file>:<line>`

**Source Context:**
```c
<source code ±10 lines>
```

**Local Variables:**
| Variable | Type | Value | Analysis |
|----------|------|-------|----------|
| `ptr` | `int*` | `0x0` | ⚠️ NULL pointer |

**Likely Cause:** `<explanation>`

## Call Chain

```
main() → init() → worker() → process_data() → 💥 CRASH
                                     ↑
                              node == NULL
```

## Root Cause Hypotheses

1. **Hypothesis 1** (High probability)
   - Evidence: ...
   - Location: `file.c:line`

2. **Hypothesis 2** (Medium probability)
   - Evidence: ...

## Recommended Investigation

1. Check why `get_node()` returned NULL:
   ```bash
   gdb-cli eval -s $SESSION "get_node(id)"
   ```

2. Verify the input parameters...

## Next Steps
- [ ] Investigation item 1
- [ ] Investigation item 2
```

## Common Debugging Patterns

### Pattern: Null Pointer Dereference

**Indicators:**
- Crash on memory access instruction
- Pointer variable is 0x0

**Investigation:**
```bash
gdb-cli registers -s $SESSION  # Check if RIP points to valid code
gdb-cli eval -s $SESSION "ptr"  # Check pointer value
```

### Pattern: Deadlock

**Indicators:**
- Multiple threads stuck in lock functions
- `pthread_mutex_lock` in backtrace

**Investigation:**
```bash
# Get all threads' backtraces
gdb-cli thread-apply -s $SESSION bt --all

# Look for circular wait patterns:
# Thread 1: waiting for lock A (held by Thread 2)
# Thread 2: waiting for lock B (held by Thread 1)
```

### Pattern: Memory Corruption

**Indicators:**
- Crash in malloc/free
- Garbage values in variables
- Stack corruption

**Investigation:**
```bash
gdb-cli memory -s $SESSION "&variable" --size 128
gdb-cli registers -s $SESSION  # Check stack pointer
```

### Pattern: Race Condition

**Indicators:**
- Non-deterministic crashes
- Issues only under load

**Investigation:**
```bash
gdb-cli threads -s $SESSION
gdb-cli thread-apply -s $SESSION locals --all
```

### Pattern: Embedded Target HardFault (Cortex-M)

**Indicators:**
- Embedded session (jlink/target mode), PC in `HardFault_Handler` or at a
  garbage address, xPSR shows exception state

**Investigation:**
```bash
gdb-cli registers -s $SESSION --names "pc,sp,lr,xpsr"   # exception state
gdb-cli bt -s $SESSION                                    # faulting chain
gdb-cli memory -s $SESSION "0xE000ED28" --size 16        # NVIC CFSR/HFSR
gdb-cli disasm -s $SESSION --count 12                    # faulting instruction
gdb-cli eval -s $SESSION "SCB->CFSR"                     # with CMSIS headers
```

Reset or resume the target through the J-Link monitor channel:

```bash
gdb-cli exec -s $SESSION "monitor reset"                 # reset + halt
gdb-cli exec -s $SESSION "monitor regs"                  # all core registers
```

## Session Management

```bash
# List active sessions
gdb-cli sessions

# Check session status
gdb-cli status -s $SESSION

# Stop session (cleanup)
gdb-cli stop -s $SESSION

# Stop session and leave the target running (embedded)
gdb-cli stop -s $SESSION --before-detach "monitor go"

# J-Link lifecycle (see Step 1): stop session AND server, or restart both
gdb-cli jlink stop --all
gdb-cli jlink restart
```

## Tips

1. **Always read source code** before drawing conclusions from variable values
2. **Use `--range`** for pagination on large thread counts or deep backtraces
3. **Use `ptype`** to understand complex data structures before examining values
4. **Check all threads** for multi-threaded issues
5. **Cross-reference types** with source code definitions using `Grep` tool

## Cross-Machine Debugging

When debugging core dumps from different machines:

```bash
# Set sysroot for library path resolution
gdb-cli load --binary ./myapp --core ./core \
  --sysroot /path/to/target/rootfs

# Source directory mapping
# Use the Read tool with absolute paths, or:
gdb-cli exec -s $SESSION "set substitute-path /build /home/user/src"
```

## Output Format Guidelines

- Use tables for variable listings
- Use code blocks for source snippets
- Use emoji indicators: ⚠️ (warning), 💥 (crash), 🔍 (investigate)
- Be specific about file:line references
- Provide actionable next steps
