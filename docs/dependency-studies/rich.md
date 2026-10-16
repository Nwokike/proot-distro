# rich 15.0.0 — exhaustive API reference

Verified 2026-10-16 against `.venv/Lib/site-packages/rich` (2698-line `console.py`).
Version: `importlib.metadata.version("rich") == "15.0.0"`. Note: `rich` exposes
**no** `__version__` attribute (verified: no `version` name in `rich.__dict__`).
License: MIT (`rich-15.0.0.dist-info/METADATA` → `License: MIT`).
Hard runtime deps (`Requires-Dist`): `markdown-it-py>=2.2.0`, `pygments>=2.13.0,<3.0.0`;
optional `ipywidgets` (`jupyter` extra). Pure-Python throughout.

Identity: terminal-rendering library. Everything renders through one `Console`
into `Segment` streams via the `__rich_console__(console, options)` protocol
(`console.py:1318` dispatches on it; anything with that method is a renderable).

## 1. Top-level package (`rich/__init__.py`)

Only seven public names (verified `dir(rich)`):

```python
get_console() -> Console            # __init__.py:23 — process-wide shared Console
reconfigure(*args, **kwargs) -> None  # __init__.py:39 — rebuilds the shared console
print(*objects, sep=" ", end="\n", file=None, flush=False) -> None
print_json(json=None, *, data=None, indent=2, highlight=True, skip_keys=False,
           ensure_ascii=False, check_circular=True, allow_nan=True,
           default=None, sort_keys=False) -> None        # __init__.py:77
inspect(obj, *, console=None, title=None, help=False, methods=False, docs=True,
        private=False, dunder=False, sort=True, all=False, value=True) -> None  # :120
load_ipython_extension(ip) -> None
```

## 2. `Console` — constructor (every param, `console.py:581`)

```python
Console(*, color_system="auto",        # auto|standard|256|truecolor|windows|None
        force_terminal=None, force_jupyter=None, force_interactive=None,
        soft_wrap=False, theme=None, stderr=False, file=None, quiet=False,
        width=None, height=None, style=None, no_color=None, tab_size=8,
        record=False,                  # enables export_*/save_* replay
        markup=True, emoji=True, emoji_variant=None, highlight=True,
        log_time=True, log_path=True, log_time_format="[%X]",
        highlighter=<ReprHighlighter>, legacy_windows=None, safe_box=True,
        get_datetime=None, get_time=None, _environ=None)
```

Properties (all `@property`, NOT methods — calling `console.size()` fails):
`size`, `width`, `height`, `options`, `is_terminal`, `is_dumb_terminal`,
`is_alt_screen`, `color_system`, `encoding`, `file`.

## 3. `Console` — every public method (with `console.py:line`)

Output:

```python
print(*objects, sep=" ", end="\n", style=None,          # :1652
      justify="default"|"left"|"center"|"right"|"full",
      overflow="fold"|"crop"|"ellipsis"|"ignore",
      no_wrap=None, emoji=None, markup=None, highlight=None,
      width=None, height=None, crop=True, soft_wrap=None,
      new_line_start=False) -> None
log(*objects, sep=" ", end="\n", style=None,            # :1947
    justify=..., emoji=None, markup=None, highlight=None,
    log_locals=False, _stack_offset=1) -> None          # timestamps + caller path
out(*objects, sep=" ", end="\n", style=None, highlight=None) -> None  # :1620, no markup/emoji
line(count=1) -> None                                   # :1136
bell() -> None                                          # :1092
clear(home=True) -> None                                # :1146
input(prompt="", *, markup=True, emoji=True,           # :2156
      password=False, stream=None) -> str
```

Contexts (`with console.status(...)`, `with console.screen()`, `with console.pager()`):

```python
status(status, *, spinner="dots", spinner_style="status.spinner",  # :1157
       speed=1.0, refresh_per_second=12.5) -> Status
screen(hide_cursor=True, style=None) -> ScreenContext   # :1263 (ScreenContext :403)
pager(pager=None, styles=False, links=False) -> PagerContext  # :1113 (:364)
```

Rules / JSON / tracebacks:

```python
rule(title="", *, characters="─", style="rule.line",   # :1589
     align="center"|"left"|"right") -> None
print_json(json=None, *, data=None, indent=2, ...) -> None  # :1758 (same kwargs as top-level)
print_exception(*, width=100, extra_lines=3, theme=None,   # :1873
                word_wrap=False, show_locals=False,
                suppress=(), max_frames=100) -> None
```

Render / measure / styles:

```python
render(renderable, options=None) -> Iterable[Segment]          # :1294
render_lines(renderable, options=None, *, style=None,
             pad=True, new_lines=False) -> List[List[Segment]] # :1345
render_str(text, *, style="", justify=..., overflow=...,       # :1409
           emoji=None, markup=None, highlight=None,
           highlighter=None) -> Text
measure(renderable, *, options=None) -> Measurement            # :1277
get_style(name, *, default=None) -> Style                      # :1470
control(*control: Control) -> None                             # :1610
use_theme(theme, *, inherit=True) -> ThemeContext
push_theme(theme, *, inherit=True) -> None
pop_theme() -> None
push_render_hook(hook: RenderHook) -> None   # RenderHook ABC at :544
pop_render_hook() -> None
show_cursor(show=True) -> bool
set_alt_screen(enable=True) -> bool
set_live(live) -> bool
clear_live() -> None                                           # :838
set_window_title(title) -> None             # (exists; unverified signature — labeled unverified)
on_broken_pipe() -> None                    # (exists; unverified signature)
```

Capture and export (require `record=True` except `capture()`):

```python
capture() -> Capture                         # :1096 — context manager
begin_capture() -> None                      # :866
end_capture() -> str                         # :870
export_text(*, clear=True, styles=False) -> str    # :2192
save_text(path, *, clear=True, styles=False) -> None  # :2224
export_html(*, theme=None, clear=True, code_format=..., inline_styles=False) -> str  # :2244
save_html(path, *, theme=None, clear=True, code_format=..., inline_styles=False)  # :2321
export_svg(*, title="Rich", theme=None, clear=True, code_format=...,  # :2352
           font_aspect_ratio=0.61, unique_id=None) -> str
save_svg(path, *, title="Rich", ...) -> None  # :2606
```

## 4. Renderables — constructors (all signatures introspected live)

```python
Table(*headers, title=None, caption=None, width=None, min_width=None,  # table.py
      box=<heavy-head box>, safe_box=None, padding=(0, 1),
      collapse_padding=False, pad_edge=True, expand=False,
      show_header=True, show_footer=False, show_edge=True, show_lines=False,
      leading=0, style="none", row_styles=None,
      header_style="table.header", footer_style="table.footer",
      border_style=None, title_style=None, caption_style=None,
      title_justify="center", caption_justify="center", highlight=False)
Table.add_column(header="", footer="", *, style=None, justify=...,  # table.py:364
                 overflow=..., width=None, min_width=None, max_width=None,
                 ratio=None, no_wrap=False) -> None
Table.add_row(*renderables, style=None, end_section=False) -> None  # :422
Table.add_section() -> None                                          # :469
Table.grid(*, padding=..., expand=False, ...) -> Table               # :253 classmethod
Table.row_count -> int; Table.expand/collapse flags (attrs; unverified full sigs)

Panel(renderable, box=<rounded>, *, title=None, title_align="center",  # panel.py
      subtitle=None, subtitle_align="center", safe_box=None, expand=True,
      style="none", border_style="none", width=None, height=None,
      padding=(0, 1), highlight=False)

Layout(renderable=None, *, name=None, size=None, minimum_size=1,  # layout.py
       ratio=1, visible=True)
# methods: split/split_row/split_column/add_split/unsplit/update/get/map/tree/render

Live(renderable=None, *, console=None, screen=False, auto_refresh=True,  # live.py
     refresh_per_second=4, transient=False, redirect_stdout=True,
     redirect_stderr=True, vertical_overflow="ellipsis",
     get_renderable=None)
# methods: start(refresh=False), stop(), update(renderable, *, refresh=False),
#          refresh(), is_started(), get_renderable()

Progress(*columns, console=None, auto_refresh=True,       # progress.py
         refresh_per_second=10, speed_estimate_period=30.0,
         transient=False, redirect_stdout=True, redirect_stderr=True,
         get_time=None, disable=False, expand=False)
Progress.add_task(description, start=True, total=100.0,
                  completed=0, visible=True, **fields) -> TaskID
Progress.update(task_id, *, total=None, completed=None, advance=None,
               description=None, visible=None, refresh=False, **fields)
Progress.advance(task_id, advance=1)
Progress.track(sequence, total=None, completed=0, task_id=None,
               description="Working...", update_period=0.1)  # iterable wrapper
Progress.wrap_file(file, total=None, *, task_id=None,
                   description="Reading...") -> BinaryIO
Progress.remove_task/reset/start_task/stop_task/start/stop/refresh()
# Column classes: TextColumn, BarColumn, SpinnerColumn, TimeElapsedColumn,
#   TimeRemainingColumn, TaskProgressColumn, MofNCompleteColumn, DownloadColumn,
#   TransferSpeedColumn, FileSizeColumn, TotalFileSizeColumn, RenderableColumn

Spinner(name, text="", *, style=None, speed=1.0)   # 73 names in rich/_spinners.py
Columns(renderables=None, padding=(0, 1), *, width=None, expand=False,  # columns.py
        equal=False, column_first=False, right_to_left=False,
        align=None, title=None)
Tree(label, *, style="tree", guide_style="tree.line", expanded=True,  # tree.py
     highlight=False, hide_root=False)
Tree.add(label, *, style=None, guide_style=None, expanded=True,
         highlight=False) -> Tree
Group(*renderables, fit=True)                        # console.py — vertical stack
Align(renderable, align="left", style=None, *,       # align.py:17
      vertical=None, pad=True, width=None, height=None)
VerticalCenter(renderable, ...)                      # align.py:242 (unverified full sig)
Padding(renderable, pad=(0,0,0,0), *, style="none", expand=True)  # padding.py
Status(status, *, console=None, spinner="dots",      # status.py
       spinner_style="status.spinner", speed=1.0, refresh_per_second=12.5)
Screen(*renderables, style=None, application_mode=False)  # screen.py
```

Box styles (`rich/box.py`): `ASCII ASCII2 ASCII_DOUBLE_HEAD SQUARE
SQUARE_DOUBLE_HEAD MINIMAL MINIMAL_HEAVY_HEAD MINIMAL_DOUBLE_HEAD ROUNDED HEAVY
HEAVY_EDGE HEAVY_HEAD DOUBLE DOUBLE_EDGE MARKDOWN SIMPLE SIMPLE_HEAD
SIMPLE_HEAVY HORIZONTALS` (verified `isupper()` names).

## 5. `Text` (`rich/text.py`, 1363 lines)

```python
Text(text="", style="", *, justify=None, overflow=None, no_wrap=None,
     end="\n", tab_size=None, spans=None)
Text.from_markup(text, *, style="", emoji=True, emoji_variant=None,
                 justify=None, overflow=None, end="\n") -> Text  # classmethod
Text.from_ansi(text, *, style="", justify=None, overflow=None,  # classmethod
               no_wrap=None, end="\n", tab_size=8) -> Text
Text.assemble(*parts: str|Text|(str, style), style="", ...) -> Text  # classmethod
Text.styled(text, style="", *, justify=None, overflow=None) -> Text  # classmethod
# NOTE: Text has NO from_markdown and NO concat (verified absent from dir(Text)).
```

Instance methods (verified list): `align append append_text append_tokens
apply_meta blank_copy cell_len copy copy_styles detect_indentation divide end
expand_tabs extend_style fit get_style_at_offset highlight_regex highlight_words
join justify markup no_wrap on overflow pad pad_left pad_right plain remove_suffix
render right_crop rstrip rstrip_end set_length spans split style stylize
stylize_before tab_size truncate with_indent_guides wrap`.

Markup system (`rich/markup.py`): `escape(markup) -> str`. Console markup tags
`[bold] [red] [link=url] [/]` resolve through the active `Theme`.
Emoji: 3608 codes (`rich/_emoji_codes.py`). Renderables protocol: anything with
`__rich_console__(console, options)`; measurables add `__rich_measure__`.

## 6. `Syntax` / `Markdown` / `JSON` (`syntax.py` 988 lines, `markdown.py` 802)

```python
Syntax(code, lexer: Lexer|str, *, theme="monokai", dedent=False,  # syntax.py
       line_numbers=False, start_line=1, line_range=None,
       highlight_lines=None, code_width=None, tab_size=4, word_wrap=False,
       background_color=None, indent_guides=False, padding=0)
Syntax.from_path(path, encoding="utf-8", lexer=None, theme="monokai",
                 dedent=False, line_numbers=False, line_range=None,
                 start_line=1, highlight_lines=None, code_width=None,
                 tab_size=4, word_wrap=False, background_color=None,
                 indent_guides=False, padding=0) -> Syntax  # classmethod
Syntax.get_theme(name: str|SyntaxTheme) -> SyntaxTheme
Syntax.highlight(code, line_range=None) -> Text
```

Pygments linkage (verified `syntax.py:24-28`):
`from pygments.lexer import Lexer`, `get_lexer_by_name`,
`guess_lexer_for_filename`, `Style as PygmentsStyle`, `get_style_by_name`.
`PygmentsSyntaxTheme`: string theme → `get_style_by_name(theme)`, unknown name
falls back to `"default"` (`syntax.py:148-150`). Built-in non-pygments themes:
`RICH_SYNTAX_THEMES = {"ansi_light": ANSI_LIGHT, "ansi_dark": ANSI_DARK}` (:123).

```python
Markdown(markup, code_theme="monokai", justify=None, style="none",
         hyperlinks=True, inline_code_lexer=None, inline_code_theme=None)
# Internals (markdown.py): parser = MarkdownIt().enable("strikethrough").enable("table")
JSON(json, indent=2, highlight=True, skip_keys=False, ensure_ascii=False,
     check_circular=True, allow_nan=True, default=None, sort_keys=False)
```

Markdown element classes (all in `rich/markdown.py`): `MarkdownElement
UnknownElement TextElement Paragraph Heading CodeBlock BlockQuote HorizontalRule
TableElement TableHeaderElement TableBodyElement TableRowElement TableDataElement
ListElement ListItem Link ImageItem MarkdownContext HeadingFormat`.
Render state: `MarkdownContext(console, options, style, inline_code_lexer,
inline_code_theme)` keeps a `StyleStack` + element `Stack`.

## 7. `Pretty` / `Traceback` / `logging` / `Inspect` / `Prompt` / `Theme`

```python
Pretty(_object, highlighter=None, *, indent_size=4, justify=None,  # pretty.py
       overflow=None, no_wrap=False, indent_guides=False, max_length=None,
       max_string=None, max_depth=None, expand_all=False, margin=0,
       insert_line=False)
pprint(_object, *, console=None, indent_guides=True, max_length=None,
       max_string=None, max_depth=None, expand_all=False) -> None
pretty_repr(_object, *, max_width=80, indent_size=4, ...) -> str
pretty.install(console=None, overflow="ignore", crop=False, ...) -> None

Traceback(trace=None, *, width=100, code_width=88, extra_lines=3,  # traceback.py
          theme=None, word_wrap=False, show_locals=False, ...)
traceback.install(*, console=None, width=100, code_width=88,      # traceback.py:84
                  extra_lines=3, theme=None, word_wrap=False,
                  show_locals=False, ...) -> excepthook

RichHandler(level=0, console=None, *, show_time=True,      # logging.py:24
            omit_repeated_times=True, show_level=True, show_path=True,
            enable_link_path=True, highlighter=None, markup=False,
            rich_tracebacks=False, tracebacks_width=None, ...)

Inspect(obj, *, title=None, help=False, methods=False, docs=True,  # _inspect.py:21
        private=False, dunder=False, sort=True, all=True, value=True)
# top-level rich.inspect: same minus obj-positional, all defaults False.

PromptBase subclasses (prompt.py): Prompt(str) IntPrompt(int)  # :304/:316
  FloatPrompt(float) Confirm(bool)  # :328/:340
Prompt.ask(prompt="", *, console=None, password=False, choices=None,
           case_sensitive=True, show_default=True, show_choices=True,
           default=..., stream=None) -> Any   # IntPrompt/FloatPrompt/Confirm inherit
class InvalidResponse(PromptError)            # :15 — raised on bad choice

Theme(styles=None, inherit=True)              # theme.py — methods: config/from_file/read
Style(*, color=None, bgcolor=None, bold=None, dim=None, italic=None,  # style.py
      underline=None, blink=None, blink2=None, reverse=None, conceal=None,
      strike=None, underline2=None, frame=None, encircle=None, overline=None,
      link=None, ...)
Control alt_screen/bell/clear/home/move/move_to/move_to_column/segment/  # control.py
      show_cursor/title  (verified constructor names)
Screen/export/capture items covered in §3.
filesize.decimal(size, *, precision=1, separator=" ") -> str
RegexHighlighter/ReprHighlighter (highlighter.py); DEFAULT_THEME in themes.py.
```

## 8. Which parts flet-cli and cookiecutter actually use (quoted sites)

flet-cli (`flet_cli/commands/`, flet pinned 1.0.4 per D-010):

- `flutter_base.py:10-15` —
  `from rich.console import Console, Group` / `from rich.panel import Panel` /
  `from rich.progress import Progress` / `from rich.prompt import Confirm` /
  `from rich.style import Style` / `from rich.theme import Theme`.
- `flutter_base.py:34-47` — the shared console:
  `console = Console(log_path=False, theme=Theme({"log.message": "green bold"}),
  force_terminal=False if no_rich_output else None)`.
- `flutter_base.py:69` — `self.progress = Progress(transient=True)`.
- `flutter_base.py:510-518` — `status = console.status(...)` wrapped in
  `Group(Panel(msg, style=error_style), status)`, updated via `self.live`.
- `flutter_base.py:165,184-185,...` — dozens of
  `console.log("Flutter executable:", self.flutter_exe, style=verbose2_style)`.
- `build.py:9-10` / `debug.py:6-7` / `test.py:10-12` / `emulators.py:6-9` —
  `from rich.console import Group` + `from rich.live import Live`;
  `emulators.py` adds `from rich.panel import Panel` +
  `from rich.table import Column, Table`.
- `create.py:6-8` — `from rich.console import Console` /
  `from rich.markup import escape` / `from rich.style import Style`.
- `clean.py:5-6` / `serve.py:6-7` — `Console` + `Style`.
- flet-desktop `__init__.py:20` — `from rich.progress import Progress`.

cookiecutter (`cookiecutter/`, build-host templating):

- `prompt.py:16` — `from rich.prompt import Confirm, InvalidResponse, Prompt,
  PromptBase`; `Prompt.ask(f"{prefix}{question}", default=...)` (:38),
  `YesNoPrompt(Confirm)` (:45), `Prompt.ask(question, password=True)` (:88),
  `Prompt.ask(prompt, choices=list(choices), ...)` (:134).

NOT used by either: `Syntax`, `Markdown`, `Live` (except flet-cli command
spinners), `Layout`, `Tree`, `Columns`, `Traceback.install`, `RichHandler`.

## 9. Fidelity: rich output vs CI logs — why `--no-rich-output` exists

`flutter_base.py:25-30` (comment + code, verbatim mechanism):

```python
# Detect the plain-output request BEFORE building the shared console: the
# `--no-rich-output` argparse flag is parsed per-command, too late to
# affect this module-level console, so check sys.argv for it here too
# (alongside the env var). Without this, the flag only suppressed emojis
# while the color + Live spinner kept going.
no_rich_output = (
    get_bool_env_var("FLET_CLI_NO_RICH_OUTPUT") or "--no-rich-output" in sys.argv
)
```

Three fidelity problems, each fixed by the flag:

1. **Spinner redraw flood.** With `force_terminal=None`, a real TTY gets the
   animated `Live` spinner; piped output (CI, cloud build) must NOT get one
   frame per line — forcing the terminal on there floods logs with thousands
   of redraws (`:38-44` comment). `force_terminal=False` disables all of it.
2. **Emoji in non-UTF8 logs.** `BaseFlutterCommand` swaps
   `"checkmark": "[green]OK[/]" if no_rich_output else "✅"` (and
   loading/success/directory, `:145-148`).
3. **Live vs plain status.** `log_status`: `console.log(status)` when
   `no_rich_output`, else `self.status.update(status)` (`:545-546`); plus
   `flutter doctor` is skipped on Windows under the flag (`:504-507`).

Rule for our CI (M5): always pass `--no-rich-output` (or set
`FLET_CLI_NO_RICH_OUTPUT=1`) in GitHub Actions so `flet build` logs stay
greppable; keep rich animation for local runs only.

## 10. How rich makes our app significantly better than Termux's proot-distro

Honest scope: rich is **host/CI-side only** — it never ships in the APK (dev
deps: flet-cli → rich; milestone M5 CI + local `flet run` output). Termux's
proot-distro prints bare `echo`/uncolored stages; our edge is ergonomics:

- **Build reports (M5):** `Table` + `Panel` + `rule` in a small
  `tools/build_report.py` wrap the `flet build apk/aab` matrix into one
  copy-pasteable summary (per-ABI result, artifact sizes via
  `filesize.decimal`, elapsed time) — Termux has no equivalent surface.
- **CI log readability:** `--no-rich-output` discipline (§9) keeps Actions logs
  clean while local builds keep spinners — strictly better than raw echo.
- **Distro tooling scripts (M3):** `Progress.track`/`wrap_file` around rootfs
  downloads in host-side helper scripts; `Confirm`/`Prompt.ask` in any
  interactive scaffolding script (same pattern cookiecutter uses).
- **Tracebacks:** `traceback.install(show_locals=True)` in dev scripts gives
  syntax-highlighted frames for `proot_service.py` debugging — Termux users
  get bare Python tracebacks.

## 11. Verification refs

- `rich/__init__.py:23,39,77,120` — top-level API; `rich/console.py:581`
  (`Console`), `:544` (`RenderHook`), `:364/:403/:310` (contexts),
  `:1113/:1157/:1263` (pager/status/screen), `:1589/:1652/:1758/:1873/:1947`
  (rule/print/print_json/print_exception/log), `:2156` (input),
  `:2192/:2224/:2244/:2321/:2352/:2606` (export/save),
  `:866/:870/:1096/:1136/:1146` (capture/line/clear).
- `rich/table.py:253/:364/:422/:469`, `rich/prompt.py:11/:15/:30/:304/:316/:328/:340`,
  `rich/align.py:17/:242`, `rich/syntax.py:24-28/:123/:148-150`,
  `rich/traceback.py:84`, `rich/logging.py:24`, `rich/_inspect.py:21`,
  `rich/_spinners.py` (73 entries), `rich/box.py` (22 style names).
- `flet_cli/commands/flutter_base.py:25-47/:69/:145-148/:504-518/:545-546`,
  `flet_cli/commands/{build,create,clean,debug,emulators,serve,test}.py`
  imports, `cookiecutter/prompt.py:16/:38/:45/:88/:134`.
- Absence claims verified by live `dir()`: no `rich.__version__`, no
  `Text.from_markdown`, no `Text.concat`, no `MarkdownIt.inline_render`
  (see markdown-it-py.md).
