"""
Russian Catalog - Русский каталог переводов
"""

RU_CATALOG = {
    # === CLI Group ===
    "cli.group.help": "GDB CLI для ИИ - Тонкий клиент CLI + встроенный Python RPC Server GDB",

    # === load command ===
    "cli.load.doc": "Загрузить core dump и запустить постоянный процесс GDB",
    "cli.load.binary_help": "Путь к исполняемому файлу",
    "cli.load.core_help": "Путь к файлу core dump",
    "cli.load.sysroot_help": "Путь sysroot (для межмашинной отладки)",
    "cli.load.solib_prefix_help": "Префикс разделяемых библиотек",
    "cli.load.source_dir_help": "Каталог исходного кода",
    "cli.load.timeout_help": "Таймаут пульса в секундах (по умолчанию: 600)",
    "cli.load.gdb_path_help": "Путь к исполняемому файлу GDB",

    # === attach command ===
    "cli.attach.doc": "Подключиться к запущенному процессу",
    "cli.attach.pid_help": "PID целевого процесса",
    "cli.attach.binary_help": "Путь к исполняемому файлу (опционально)",
    "cli.attach.scheduler_locking_help": "Включить scheduler-locking",
    "cli.attach.non_stop_help": "Включить режим non-stop",
    "cli.attach.timeout_help": "Таймаут пульса в секундах (по умолчанию: 600)",
    "cli.attach.allow_write_help": "Разрешить изменение памяти",
    "cli.attach.allow_call_help": "Разрешить вызовы функций",

    # === target command ===
    "cli.target.remote_help": "Адрес удалённой цели (host:port или [ipv6]:port)",
    "cli.target.binary_help": "Путь к исполняемому файлу (опционально)",
    "cli.target.remote_mode_help": "Режим удалённого подключения (remote/extended-remote)",
    "cli.target.scheduler_locking_help": "Включить scheduler-locking",
    "cli.target.non_stop_help": "Включить режим non-stop",
    "cli.target.timeout_help": "Таймаут пульса в секундах (по умолчанию: 600)",
    "cli.target.allow_write_help": "Разрешить изменение памяти",
    "cli.target.allow_call_help": "Разрешить вызовы функций",

    # === eval-cmd command ===
    "cli.eval_cmd.doc": "Вычислить выражение C/C++",
    "cli.eval_cmd.session_help": "ID сессии",
    "cli.eval_cmd.max_depth_help": "Лимит глубины рекурсии",
    "cli.eval_cmd.max_elements_help": "Лимит элементов массива",
    "cli.eval_cmd.deref_help": "Автоматически разыменовывать указатели",

    # === threads command ===
    "cli.threads.doc": "Список потоков",
    "cli.threads.session_help": "ID сессии",
    "cli.threads.range_help": "Диапазон потоков (напр., 3-10)",
    "cli.threads.limit_help": "Максимальное количество",
    "cli.threads.filter_state_help": "Фильтр по состоянию (running/stopped)",

    # === bt command ===
    "cli.bt.doc": "Получить backtrace",
    "cli.bt.session_help": "ID сессии",
    "cli.bt.thread_help": "Указать ID потока",
    "cli.bt.limit_help": "Максимальное количество фреймов",
    "cli.bt.full_help": "Включить локальные переменные",
    "cli.bt.range_help": "Диапазон фреймов (напр., 5-15)",

    # === frame command ===
    "cli.frame.doc": "Выбрать стековый фрейм",
    "cli.frame.session_help": "ID сессии",

    # === locals-cmd command ===
    "cli.locals_cmd.doc": "Получить локальные переменные",
    "cli.locals_cmd.session_help": "ID сессии",
    "cli.locals_cmd.thread_help": "ID потока",
    "cli.locals_cmd.frame_help": "Номер фрейма",

    # === exec command ===
    "cli.exec.doc": "Выполнить сырую команду GDB",
    "cli.exec.session_help": "ID сессии",
    "cli.exec.safety_level_help": "Уровень безопасности (readonly/readwrite/full)",

    # === stop command ===
    "cli.stop.doc": "Остановить сессию и безопасно выйти из GDB",
    "cli.stop.session_help": "ID сессии",
    "cli.stop.before_detach_help": (
        "Команды GDB, выполняемые перед detach, по одной на строку "
        "(например, 'monitor go', чтобы оставить цель запущенной)"
    ),
    "cli.stop.force_help": "Принудительно завершить процесс GDB, если RPC stop не удался",
    "cli.stop.cleanup_failed": "Не удалось очистить сессию: {session_id}",

    # === sessions command ===
    "cli.sessions.doc": "Список всех активных сессий",

    # === status command ===
    "cli.status.doc": "Проверить статус сессии",
    "cli.status.session_help": "ID сессии",

    # === eval-element command ===
    "cli.eval_element.doc": "Доступ к элементу массива/контейнера",
    "cli.eval_element.session_help": "ID сессии",
    "cli.eval_element.index_help": "Индекс элемента",
    "cli.eval_element.max_depth_help": "Лимит глубины рекурсии",

    # === thread-apply command ===
    "cli.thread_apply.doc": "Пакетные операции над потоками",
    "cli.thread_apply.session_help": "ID сессии",
    "cli.thread_apply.threads_help": "Список ID потоков (напр., 1,3,5)",
    "cli.thread_apply.all_help": "Применить ко всем потокам",

    # === args command ===
    "cli.args.doc": "Получить аргументы функции",
    "cli.args.session_help": "ID сессии",
    "cli.args.thread_help": "ID потока",
    "cli.args.frame_help": "Номер фрейма",

    # === registers command ===
    "cli.registers.doc": "Просмотреть значения регистров",
    "cli.registers.session_help": "ID сессии",
    "cli.registers.names_help": "Имена регистров (через запятую, напр., rax,rbx,rip)",
    "cli.registers.thread_help": "ID потока",
    "cli.registers.frame_help": "Номер фрейма",

    # === memory command ===
    "cli.memory.doc": "Проверить содержимое памяти",
    "cli.memory.session_help": "ID сессии",
    "cli.memory.size_help": "Байты для чтения (по умолчанию: 64, макс: 4096)",
    "cli.memory.fmt_help": "Формат вывода (hex/bytes/string)",

    # === ptype command ===
    "cli.ptype.doc": "Просмотреть информацию о типе выражения",
    "cli.ptype.session_help": "ID сессии",

    # === thread-switch command ===
    "cli.thread_switch.doc": "Переключить текущий поток",
    "cli.thread_switch.session_help": "ID сессии",

    # === up command ===
    "cli.up.doc": "Переместиться к вызывающему в стеке",
    "cli.up.session_help": "ID сессии",

    # === down command ===
    "cli.down.doc": "Переместиться к вызываемому в стеке",
    "cli.down.session_help": "ID сессии",

    # === sharedlibs command ===
    "cli.sharedlibs.doc": "Просмотреть загруженные разделяемые библиотеки",
    "cli.sharedlibs.session_help": "ID сессии",

    # === disasm command ===
    "cli.disasm.doc": "Дизассемблировать",
    "cli.disasm.session_help": "ID сессии",
    "cli.disasm.start_help": "Начальный адрес или имя функции (по умолчанию: текущий PC)",
    "cli.disasm.count_help": "Количество инструкций (по умолчанию: 20)",
    "cli.disasm.thread_help": "ID потока",
    "cli.disasm.frame_help": "Номер фрейма",

    # === env-check command ===
    "cli.env_check.doc": "Проверка окружения: версия GDB, права ptrace, версия Python",

    # === jlink command group ===
    "cli.jlink.doc": "Управление JLinkGDBServer с автоматическим запуском сессии GDB",
    "cli.jlink.epilog": (
        "\b\n"
        "Соответствие аргументов JLinkGDBServer и опций gdb-cli:\n"
        "  -device DEV             -> -d, --device DEV\n"
        "  -select SELECT          -> --select usb=<serial|nickname> | ip=HOST:PORT\n"
        "  -if IF                  -> --if SWD|JTAG\n"
        "  -speed SPEED            -> --speed kHz (не указывать = авто)\n"
        "  -port PORT              -> --port (не указывать = свободный порт)\n"
        "  -swoport/-telnetport/   -> --extra-arg\n"
        "  -RTTTelnetPort\n"
        "  -rtos PLUGIN            -> --extra-arg -rtos\n"
        "                            --extra-arg GDBServer/RTOSPlugin_<name>\n"
        "  -x/-xc FILE             -> --extra-arg -x --extra-arg <gdbinit>\n"
        "  -jlinkscriptfile FILE   -> --extra-arg\n"
        "  -jtagconf/-excdbg/      -> --extra-arg\n"
        "  -powertarget\n"
        "  -USB <sn> / -IP <host>  -> используйте --select\n"
        "  -singlerun/-noreset/    -> --extra-arg\n"
        "  -log/-settingsfile\n"
        "\n"
        "Всегда задаётся gdb-cli (нельзя переопределить):\n"
        "  -nogui -nolocalhostonly -halt -nosilent -vd -noir -notimeout\n"
        "\n"
        "Зарезервированные (нельзя передать через --extra-arg):\n"
        "  -select, -port, -device, -if, -gui, -nogui\n"
        "\n"
        "Выполните 'gdb-cli jlink start --help' для всех опций."
    ),
    "cli.jlink.start.doc": "Запустить JLinkGDBServer и подключить GDB",
    "cli.jlink.start_epilog": (
        "\b\n"
        "Соответствие аргументов JLinkGDBServer (см. также справку группы):\n"
        "  -device <name>          -d/--device (обязателен; имя МК, известное\n"
        "                          J-Link, напр. nRF54L15_M33)\n"
        "  -select <sel>           --select usb=<serial|nickname> |\n"
        "                          ip=HOST:PORT\n"
        "  -if <SWD|JTAG|FINE|     --if (по умолчанию SWD)\n"
        "    2-wire-JTAG-PIC32>\n"
        "  -speed <kHz|auto>       --speed (не указывать = авто)\n"
        "  -port <n>               --port (не указывать = свободный порт)\n"
        "  -swoport <n>            --extra-arg -swoport --extra-arg <n>\n"
        "  -telnetport <n>         --extra-arg -telnetport --extra-arg <n>\n"
        "  -RTTTelnetPort <n>      --extra-arg -RTTTelnetPort --extra-arg <n>\n"
        "  -rtos <plugin>          --extra-arg -rtos --extra-arg <plugin>\n"
        "                          (RTOS thread awareness; on Linux use\n"
        "                          GDBServer/RTOSPlugin_<name> e.g.\n"
        "                          GDBServer/RTOSPlugin_FreeRTOS — bare\n"
        "                          'FreeRTOS' fails to resolve)\n"
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
        "  -JLinkDevicesXMLPath    --extra-arg (устарело SEGGER)\n"
        "  -USB <sn> / -IP <h>     используйте --select usb=<sn> / ip=<h>:<port>\n"
        "\n"
        "gdb-cli всегда задаёт (нельзя переопределить):\n"
        "  -nogui -nolocalhostonly -halt -nosilent -vd -noir -notimeout\n"
        "\n"
        "Зарезервировано через --extra-arg: -select -port -device -if -gui -nogui.\n"
        "\n"
        "Прочие флаги JLinkGDBServer передаются через --extra-arg как есть\n"
        " (по одному токену на --extra-arg)."
    ),
    "cli.jlink.stop.doc": "Остановить экземпляр(ы) JLinkGDBServer",
    "cli.jlink.restart.doc": "Перезапустить экземпляр JLinkGDBServer (использует сохранённые настройки сессии GDB)",
    "cli.jlink.status.doc": "Показать состояние экземпляров JLinkGDBServer",
    "cli.jlink.devices.doc": "Список подключённых отладчиков J-Link",
    "cli.jlink.device_help": "Имя целевого устройства (например, nRF54L15_M33)",
    "cli.jlink.select_help": "Выбор отладчика: usb=<серийный номер|никнейм> или ip=HOST:PORT",
    "cli.jlink.binary_help": "Путь к исполняемому файлу для сессии GDB (опционально)",
    "cli.jlink.gdb_path_help": "Путь к исполняемому файлу GDB",
    "cli.jlink.jlink_path_help": "Путь к исполняемому файлу JLinkGDBServer",
    "cli.jlink.speed_help": "Скорость интерфейса в кГц (по умолчанию: авто)",
    "cli.jlink.interface_help": "Отладочный интерфейс (SWD/JTAG)",
    "cli.jlink.port_help": "Порт GDB Server (по умолчанию: свободный порт)",
    "cli.jlink.allow_write_help": "Разрешить изменение памяти",
    "cli.jlink.allow_call_help": "Разрешить вызовы функций",
    "cli.jlink.timeout_help": "Таймаут пульса GDB в секундах (по умолчанию: 600)",
    "cli.jlink.extra_arg_help": "Дополнительный необработанный аргумент JLinkGDBServer (можно повторять)",
    "cli.jlink.jlink_id_help": "ID экземпляра J-Link",
    "cli.jlink.all_help": "Применить ко всем экземплярам",
    "cli.jlink.select_required": "Не указан --select (используйте usb=<серийный номер|никнейм> или ip=HOST:PORT)",
    "cli.jlink.usb_selector_required": (
        "Нельзя указывать только --select usb; выполните 'gdb-cli jlink devices' "
        "и используйте usb=<серийный номер> или usb=<никнейм>"
    ),
    "cli.jlink.ip_selector_required": "Неверное значение --select ip; используйте ip=HOST:PORT",
    "cli.jlink.device_required": "Не указан --device (JLinkGDBServer требует имя устройства)",
    "cli.jlink.port_busy": "Порт {port} уже используется",
    "cli.jlink.no_instance": "Экземпляр J-Link не найден: {instance_id}",
    "cli.jlink.ambiguous_instance": "Запущено несколько экземпляров J-Link; используйте --jlink-id: {instances}",
    "cli.jlink.start_failed": "Не удалось запустить JLinkGDBServer",
    "cli.jlink.connect_failed": "Не удалось установить сессию GDB",
    "cli.jlink.stop_failed": "Не удалось остановить экземпляр J-Link",
    "cli.jlink.restart_failed": "Не удалось перезапустить экземпляр J-Link",
    "cli.jlink.devices_failed": "Не удалось перечислить устройства J-Link: {reason}",
    "cli.jlink.process_exited": "JLinkGDBServer неожиданно завершился. Последние строки журнала:\n{tail}",
    "cli.jlink.ready_timeout": "JLinkGDBServer не открыл порт {port} за {timeout} секунд",
    "cli.jlink.no_instances": "Нет запущенных экземпляров J-Link",
    "cli.jlink.select_invalid": (
        "Неверное значение --select: {value} "
        "(допустимые формы: usb=<серийный номер|никнейм> или ip=HOST:PORT)"
    ),
    "cli.jlink.extra_arg_protected": (
        "Дополнительный аргумент {arg} зарезервирован gdb-cli и не может быть переопределён"
    ),
    "cli.jlink.session_not_ready": (
        "Сессия GDB не перешла в состояние готовности "
        "(последнее состояние: {state}, последняя ошибка: {error})"
    ),
    "cli.jlink.port_invalid": "Неверный порт: {port} (должен быть 1-65535)",

    # === Errors ===
    "errors.session_not_found": "Сессия не найдена: {session_id}",
    "errors.connection_error": "Ошибка соединения",
    "errors.variable_not_found.suggestion": "Проверьте правильность имени переменной, используйте 'info locals' для просмотра переменных в текущей области видимости",
    "errors.syntax_error.suggestion": "Проверьте синтаксис выражения, убедитесь, что формат C/C++ правильный",
    "errors.invalid_thread.suggestion": "Используйте команду 'threads' для просмотра списка доступных потоков",
    "errors.invalid_frame.suggestion": "Используйте команду 'bt' для просмотра списка фреймов",
    "errors.memory_access_failed.suggestion": "Целевая область памяти недоступна, переменная может быть оптимизирована",
    "errors.no_debug_info.suggestion": "Попробуйте загрузить debuginfo: 'dnf debuginfo-install' или проверьте файл .debug",
    "errors.process_not_found.suggestion": "Проверьте существование процесса: 'ps aux | grep <имя_процесса>'",
    "errors.ptrace_denied.suggestion": "Выполните: 'echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope'",
    "errors.command_blocked.suggestion": "Команда заблокирована политикой безопасности, используйте флаг --allow-write или --allow-call",
    "errors.command_timeout.suggestion": "Таймаут команды, попробуйте увеличить --timeout или упростить операцию",
    "errors.load_timeout.suggestion": "Таймаут загрузки core файла, файл может быть слишком большим, попробуйте увеличить таймаут",
    "errors.socket_not_found.suggestion": "Сессия GDB могла завершиться, перезапустите 'gdb-cli load' или 'gdb-cli attach'",
    "errors.connection_refused.suggestion": "GDB RPC Server не отвечает, проверьте, запущен ли процесс GDB",

    # === Environment Check ===
    "env_check.gdb_not_found.error": "GDB не найден в PATH",
    "env_check.gdb_not_found.suggestion": "Установите GDB: 'brew install gdb' (macOS) или 'yum install gdb' (Linux)",
    "env_check.gdb_below_minimum.error": "Версия GDB {version} ниже минимальной {minimum}",
    "env_check.gdb_below_minimum.suggestion": "Обновите GDB до версии 9.0 или выше",
    "env_check.gdb_version_warning": "Версия GDB {version} поддерживается, но рекомендуется {recommended}+",
    "env_check.gdb_recommended_suggestion": "Рекомендуется обновить до GDB 15+ для лучшей совместимости с rockylinux/el9",
    "env_check.ptrace_restricted.warning": "ptrace ограничен (scope=1). Можно подключаться только к дочерним процессам.",
    "env_check.ptrace_heavily_restricted.error": "ptrace сильно ограничен (scope={scope})",
    "env_check.ptrace_heavily_restricted.suggestion": "Выполните: echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope",
    "env_check.ptrace_sysctl_suggestion": "Или выполните: sysctl kernel.yama.ptrace_scope=0",
    "env_check.ptrace_scope_read_error.warning": "Невозможно прочитать ptrace_scope (доступ запрещён)",
    "env_check.debuginfo_not_found.suggestion": "Бинарный файл лишён отладочной информации (no debug info)",
    "env_check.debuginfo_install_rhel": "RHEL/CentOS: dnf debuginfo-install {package}",
    "env_check.debuginfo_install_ubuntu": "Ubuntu/Debian: apt-get install {package}-dbgsym",
    "env_check.debuginfo_install_fedora": "Fedora: dnf install {package}-debuginfo",
    "env_check.debuginfo_separate_file": "Или используйте отдельный .debug файл: add-symbol-file /path/to/{package}.debug",

    # === Runtime messages ===
    "errors.session_no_socket": "Сессия не имеет сокета: {session_id}",
    "cli.load.session_reused_message": "Сессия для этого core-файла уже существует",
    "cli.load.failed": "Не удалось запустить GDB",
    "cli.attach.session_reused_message": "Сессия для этого PID уже существует",
    "cli.attach.failed": "Не удалось подключиться к процессу",
    "cli.target.invalid_format": "Неверный формат удалённого адреса: {remote}",
    "cli.target.session_reused_message": "Сессия для этой удалённой цели уже существует",
    "cli.target.failed": "Не удалось подключиться к цели",
    "cli.status.gdb_loading_message": "Процесс GDB жив, пока не отвечает",
    "cli.status.gdb_unresponsive_message": "Процесс GDB жив, но больше не отвечает",
    "cli.status.session_dead": "Сессия завершена",
    "cli.status.gdb_process_dead": "Процесс GDB {pid} больше не существует",
    "cli.thread_apply.require_target": "Необходимо указать --all или --threads",

    # === JSON output hints ===
    "hints.threads_pagination": "используйте 'threads --range START-END' для конкретных потоков",
    "hints.bt_pagination": "используйте 'bt --range START-END' для конкретных фреймов",
    "hints.eval_large_array": "используйте 'eval-element' для доступа к конкретным индексам массива",
}
