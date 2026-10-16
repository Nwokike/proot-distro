# flet 1.0.4 — exhaustive API reference (dependency study)

> Scope: installed wheel `flet==1.0.4` ONLY (`D-010`: stay on stable 1.0.4; 1.1.0 exists
> only as `1.1.0.dev0` pre-release). Owner rule: **every API claim below is verified**
> against installed source (`SP = .venv/Lib/site-packages/flet/`) with `file:line`, or
> against live introspection with the venv python. Anything not verifiable is labeled
> **unverified**. No signatures are guessed.
> Introspection interpreter: `.venv/Scripts/python.exe` (CPython 3.14, Windows).

---

## 1. Identity

| Fact | Value | Evidence |
|---|---|---|
| Package / version | `flet 1.0.4` | `SP/flet/version.py:19` (`flet_version = "1.0.4"`), `SP/flet/__init__.py` re-exports it as `__version__` |
| License | `Apache-2.0` | `flet-1.0.4.dist-info/METADATA`: `License-Expression: Apache-2.0` |
| Wheel purity | **Pure-Python**: `Root-Is-Purelib: true`, `Tag: py3-none-any`, generator `setuptools (84.0.0)` | `flet-1.0.4.dist-info/WHEEL` (all 4 lines quoted verbatim) |
| Size on disk | **279 `.py` files**; 306 files / 3.2 MB pristine (408 files / ~4.2 MB after first import populates `__pycache__`); 27 directories | `find` + `du` over `SP/flet` (both runs recorded; delta is bytecode cache) |
| Pinned Flutter version | **`3.44.8`** | `SP/flet/version.py:29` (`flutter_version = "3.44.8"`); resolved via `get_flutter_version()` at `version.py:138` |
| `requires-python` | `>=3.10` | `METADATA`: `Requires-Python: >=3.10` |
| Public export count | **538 names** in `flet.__all__` | live: `len(flet.__all__) == 538` |
| Runtime deps (base install) | `oauthlib>=3.2.2` + `httpx>=0.28.1` (both skipped on Emscripten), `repath>=0.9.0`, `msgpack>=1.1.0`, `typing-extensions` (py<3.11) | `METADATA` `Requires-Dist` lines |
| Optional extras | `cli` → `flet-cli==1.0.4`; `desktop` → `flet-desktop==1.0.4`; `web` → `flet-web==1.0.4`; `all` → all three; `test` → `pytest`, `pytest-asyncio`, `numpy`, `pillow`, `scikit-image` | `METADATA` (`Provides-Extra` + `Requires-Dist`) |
| Lockstep family | `flet-cli==1.0.4`, `flet-desktop==1.0.4`, `flet-ads==1.0.4` co-installed in this venv; per D-004 the family bumps atomically | venv listing; `docs/decisions.md` D-004 |
| `py.typed` | present (`SP/flet/py.typed`) — package ships inline types | directory listing |

### 1.1 Lazy-loading semantics (how `import flet` stays cheap)

- `SP/flet/__init__.py` header comment (lines 1–7): *"The public API is imported
  lazily (PEP 562). `import flet` no longer executes the full ~270-module package;
  each name is imported on first access and cached into module globals."*
- Mechanism: `__all__` literal at `__init__.py:738` (538 entries); `_LAZY: dict[str,str]`
  name→module-path map at `__init__.py:1280`; `__getattr__` at `__init__.py:1821`
  (`importlib.import_module`, `getattr`, submodule fallback, then `globals()[name] =
  value` cache); `__dir__` returns `list(__all__)`.
- The `if TYPE_CHECKING:` block (top of `__init__.py`) exists **only for type
  checkers/IDEs** — zero runtime cost.
- Practical consequences for our app: (a) cold-start cost is pay-per-control;
  (b) `ft.X` attribute access has a one-time import hit, then a dict hit;
  (c) `dir(flet)` / `flet.__all__` is the authoritative export list — used to
  produce §2 (sorted dump, 538 names, verified live).

---

## 2. Complete public API inventory

Module tree (relative to `SP/flet/`, 279 `.py` files; full sorted list verified via
`find`): `__init__.py`, `app.py`, `cli.py`, `data_channel.py`, `pytest_plugin.py`,
`version.py`, `auth/` (8: `authorization`, `authorization_service`, `group`,
`oauth_provider`, `oauth_token`, `user`, `providers/{auth0,azure,github,google}_oauth_provider`),
`canvas/` (`__init__` only — re-export shim, see §2.6), `components/` (12:
`component`, `component_decorator`, `component_owned`, `memo`, `observable`,
`public_utils`, `router`, `utils`, `hooks/{hook,use_callback,use_context,use_dialog,use_effect,use_memo,use_ref,use_state}`),
`controls/` (core files: `action_control`, `adaptive_control`, `alignment`,
`animation`, `base_control`, `base_page`, `blur`, `border`, `border_radius`, `box`,
`buttons`, `client_action`, `colors`, `context`, `control`, `control_event`,
`control_state`, `device_info`, `dialog_control`, `duration`, `embed_json_encoder`,
`events`, `exceptions`, `geometry`, `gradients`, `icon_data`, `id_counter`, `keys`,
`layout_control`, `margin`, `multi_view`, `object_patch`, `padding`, `page`,
`painting`, `query_string`, `ref`, `scrollable_control`, `template_route`,
`text_style`, `theme`, `transform`, `types`, `value_types`; subpackages `core/`
(38 modules incl. `canvas/` 14), `cupertino/` (26), `material/` (52), `services/`
(22)), `messaging/` (7), `pubsub/` (3), `security/` (1), `testing/` (5),
`utils/` (22), `fastapi/` (`__init__` only).

### 2.1 Entry point — `flet.app` (`SP/flet/app.py`, 753 lines)

```python
def run(
    main: Callable[[Page], Any | Awaitable[Any]],
    before_main: Callable[[Page], Any | Awaitable[Any]] | None = None,
    name: str = "",
    host: str | None = None,
    port: int = 0,
    view: AppView | None = AppView.FLET_APP,          # app.py:74
    assets_dir: str | None = "assets",                # DEFAULT_ASSETS_DIR, app.py:33
    upload_dir: str | None = None,
    web_renderer: WebRenderer = WebRenderer.AUTO,     # app.py:78
    route_url_strategy: RouteUrlStrategy = RouteUrlStrategy.PATH,
    no_cdn: bool | None = False,
    export_asgi_app: bool | None = False,             # run() only
) -> ...  # returns FastAPI ASGI app when export_asgi_app=True (app.py:99-112)
```

```python
async def run_async(  # app.py:150 — identical params MINUS export_asgi_app
    main, before_main=None, name="", host=None, port=0,
    view=AppView.FLET_APP, assets_dir="assets", upload_dir=None,
    web_renderer=WebRenderer.AUTO, route_url_strategy=RouteUrlStrategy.PATH,
    no_cdn=False,
)
```

(Signatures verbatim from live `inspect.signature`; defaults cross-checked at
`app.py:68-80` / `150-161`.) Docstring notes: `assets_dir` = app assets dir;
`upload_dir` = dir for uploaded files; `no_cdn` = don't load CanvasKit/Pyodide/fonts
from CDN. `before_main` runs before `main`. `name` labels the session.
`FLET_LOG_LEVEL` applied via `__configure_logging_from_env` (`app.py:48-65`;
unknown value → warning, not crash).

- `AppView` (`controls/types.py:22`): `FLET_APP`, `FLET_APP_HIDDEN`, `FLET_APP_WEB`,
  `WEB_BROWSER` (live-verified).
- `WebRenderer` (`types.py:49`): `AUTO`, `CANVAS_KIT`, `SKWASM` (live-verified).
- `RouteUrlStrategy` (`types.py:90`): `HASH`, `PATH` (live-verified).
- `flet.cli:main()` (`SP/flet/cli.py:4`) — thin shim delegating to `flet-cli`.
- `export_asgi_app=True` path builds the ASGI app via `__get_assets_dir_path(...,
  relative_to_cwd=True)` (`app.py:112-124`).

### 2.2 `Page` / `BasePage` (`controls/page.py` 1432 lines, `controls/base_page.py` 864 lines)

`Page` declared at `page.py:483` as `@control("Page", isolated=True,
post_init_args=2) class Page(BasePage)`. `BasePage` at `base_page.py:136` extends
`AdaptiveControl`. `MultiView(BasePage)` at `controls/multi_view.py:10`.

**BasePage fields** (`base_page.py`, absolute lines): `views: list[View]` (:159),
`theme_mode: ThemeMode = SYSTEM` (:169), `theme` (:174), `dark_theme` (:181),
`theme_animation_style` (:186), `locale_configuration` (:197),
`show_semantics_debugger: bool` (:202), `title: str | None` (:208),
`enable_screenshots: bool` (:213), `on_resize` (:218), `on_media_change` (:232),
`media: PageMediaData` (:237), `width/height: Number | None` (:255/:267, the
viewport size — read-only-ish platform values).

**BasePage methods** (`base_page.py`): `update(*controls)` (:320), `add(*controls)`
(:334), `insert(at, *controls)` (:346), `remove(*controls)` (:356),
`remove_at(index)` (:364), `clean()` (:371), `show_dialog(dialog)` (:402),
`pop_dialog()` (:427); properties `overlay` (:580), `controls` (:590),
`appbar: AppBar | CupertinoAppBar | None` (:603), `bottom_appbar` (:619),
`navigation_bar` (:632), `drawer`/`end_drawer` (:650/:663),
`decoration`/`foreground_decoration` (:676/:689), `floating_action_button` (:702)
+ `floating_action_button_location` (:715), `horizontal_alignment` (:732),
`vertical_alignment` (:745), `spacing: Number` (:758), `padding` (:771),
`bgcolor` (:784), `scroll: ScrollMode | Scrollbar | None` (:797),
`auto_scroll: bool` (:810), `services: list[Service]` (:823),
`__contains__` (:835), `init()` (:850). Media helpers `padding / view_padding /
view_insets / device_pixel_ratio / orientation` at :70–:93.

**Page fields** (`page.py:492-714`, absolute lines): `sess: InitVar[Session]` (:492),
`multi_views` (:497), `window: Window` (:502), `route: str = "/"` (:508),
`web/pwa/debug/wasm/test/multi_view/pyodide: bool` (:516–:563),
`platform_brightness` (:571), `client_ip` (:579), `client_user_agent` (:587),
`platform: PagePlatform | None` (:595), `fonts: dict[str,str] | None` (:600),
events `on_platform_brightness_change` (:614), `on_locale_change` (:621),
`on_app_lifecycle_state_change` (:629), `on_route_change` (:636),
`on_view_pop` (:642), `on_views_pop_until` (:648), `on_keyboard_event` (:655),
`on_connect` (:660), `on_disconnect` (:670), `on_close` (:676), `on_login` (:682),
`on_logout` (:690), `on_error` (:695), `on_multi_view_add` (:700),
`on_multi_view_remove` (:708), `_services: ServiceRegistry` (:714).
`ServiceRegistry` itself at `page.py:92` (`@control("ServiceRegistry")`).

**Page methods** (`page.py`): `register_service(service)` (:120),
`unregister_services()` (:228 — refcount pruning, see §3.7),
`get_control(id)` (:736), `render(...)` (:750), `render_views(...)` (:775),
`schedule_update()` (:812), `update(*controls)` (:819), `error(message)` (:856),
`before_event(e)` (:866), `app_visible` property (:897),
`run_task(handler, *args, **kwargs) -> Future` (:929 — coroutine fn run on the
connection loop via `asyncio.run_coroutine_threadsafe`),
`run_thread(handler, ...)` (:991 — plain fn on the page executor),
`navigate(route, **kwargs)` (:1093 — sync wrapper scheduling `push_route`),
`get_upload_url(file_name, expires) -> str` (:1172 — presigned upload URL),
`login(provider, fetch_user=True, fetch_groups=False, scope=None, saved_token=None,
on_open_authorization_url=None, complete_page_html=None, redirect_to_page=False,
authorization=None)` (:1193, async), `logout()` (:1292 — clears auth ctx, fires
`on_logout`); read-only props `session` (:1303), `query: QueryString` (:1312),
`url` (:1319), `name` (:1326), `loop` (:1333), `executor` (:1340),
`auth: Authorization | None` (:1347), `pubsub: PubSubClient` (:1354).
Page-scoped event classes (`page.py:266-477`): `RouteChangeEvent`,
`PlatformBrightnessChangeEvent`, `LocaleChangeEvent`, `ViewPopEvent`,
`ViewsPopUntilEvent`, `KeyboardEvent` (fields `key/shift/ctrl/alt/meta`, :364-384),
`LoginEvent` (fields `error/error_description`, :399-404), `InvokeMethodResults`
(`method_id/result/error`, :419-429), `AppLifecycleStateChangeEvent`
(`state: AppLifecycleState`, :444), `MultiViewAddEvent` (`view_id/initial_data`,
:458-463), `MultiViewRemoveEvent` (`view_id`, :477).

### 2.3 Control model (`base_control.py` 579 lines, `control.py` 142, `layout_control.py` 320)

- `@control` decorator — two overloads (`base_control.py:62-81`); full form
  (`base_control.py:73-81`, verified):
  `control(dart_widget_name=None, *, isolated=None, post_init_args=1,
  categories=None, tags=None, **dataclass_kwargs)`. Applies dataclass transform +
  wire wiring; `categories`/`tags` feed gallery/tooling metadata.
- `@value` / `Value` (`base_control.py`, exported): value-type descriptor system;
  implementation in `controls/value_types.py:29` (`Prop`), `:140` (`_ValueMeta`),
  `:148` (`Value`), `:160` (`value(...)` factory).
- `BaseControl` (`base_control.py:186`, `@dataclass(kw_only=True)`): internals
  `_values/_dirty: dict` (:197/:204), `_i: int` wire id (:212), `_c: str` wire name
  (:217); lifecycle `__post_init__(ref)` (:242), `parent` (:285), `page` (:299),
  `is_isolated` (:315), `init()` (:324), `build()` (:337), `before_update()`
  (:344), `before_event(e)` (:370), `did_mount()` (:379), `will_unmount()` (:389),
  `get_data_channel(channel_id)` (:399), `update()` (:432 — serializes the diff
  patch for this subtree), `_migrate_state` (:556), `skip_field()` helper (:48).
- `Control(BaseControl)` (`controls/control.py`, whole file): `expand: bool|int |
  None` (validated `V.instance_of((bool,int))`), `expand_loose: bool = False`,
  `col: ResponsiveNumber = 12` (number or per-breakpoint dict; `0` hides),
  `opacity` (validated `V.between`), `tooltip: TooltipValue`, `badge: BadgeValue`,
  `visible=True`, `disabled=False`, `rtl=False`.
- `LayoutControl` (`layout_control.py` fields): `width/height/left/top/right/bottom:
  Number|None`, `align: Alignment|None` (:112), `margin: MarginValue` (:117),
  `rotate: RotateValue` (:122), `scale: ScaleValue` (:145), `offset: OffsetValue`
  (:169), `flip: Flip` (:207), `transform: Transform` (:214),
  `aspect_ratio: Number|None` (:221), eight `animate_*:
### 3.6 Storage (`StoragePaths`, `storage_paths.py` 222 lines) + env-var mirror

Full method list (all `async`, all raise `FletUnsupportedPlatformException` on web):

| Method → line | Returns | Env mirror (docstring-cited) |
|---|---|---|
| `get_application_cache_directory` :20 | `str` | `FLET_APP_STORAGE_CACHE` (:27) |
| `get_application_documents_directory` :41 | `str` | `FLET_APP_STORAGE_DATA` (:72) |
| `get_application_support_directory` :65 | `str` | *(docstring names the dir; env mirror is `FLET_APP_STORAGE_DATA`-adjacent — see Unverified U-3)* |
| `get_downloads_directory` :87 | `str \| None` | — |
| `get_external_cache_directories` :105 | `list[str] \| None` | — |
| `get_external_storage_directories` :124 | `list[str] \| None` | — |
| `get_library_directory` :143 | `str` | — |
| `get_external_storage_directory` :162 | `str \| None` | — |
| `get_temporary_directory` :178 | `str` | `FLET_APP_STORAGE_TEMP` (:188) |
| `get_console_log_filename` :202 | `str` | `FLET_APP_CONSOLE` (:210) |

**This is the M3 storage answer**: rootfs/tarballs/OCI layers live under
`get_application_support_directory()` (or documents for user-visible data);
`PD_PROOT_BIN`/`PROOT_LOADER`/`TERMUX__*` point into those paths. Sync env access
(`os.getenv("FLET_APP_STORAGE_DATA")`) works wherever `await` is awkward.

### 3.7 Service lifecycle & refcount pruning (`page.py:92-260`)

- `ServiceRegistry(Service)` — `_services: list[Service]` (`page.py:102`),
  `_auto_register: ClassVar[bool] = False` (`page.py:107`).
- `register_service` (`page.py:120`): appends under `self._lock`; if page not yet
  sent, defers to page payload; else pushes an update with snapshot/restore
  (`__snapshot_update_state`, `page.py:154`) so a failed send rolls back diff
  bookkeeping; `__was_sent` (`page.py:215`) checks the session index.
- `unregister_services` (`page.py:228`): **refcount pruning** — keeps services with
  `sys.getrefcount(service) > min_refs` where `min_refs = 3 if sys.version_info >=
  (3,14) else 4`; removals trigger `__internal_update()` (`page.py:249`), which
  preserves the user's update-called flag via `context.was_update_called()`.
- **Project rule (M4)**: every screen that adds a session-scoped service
  (`SharedPreferences`, `Wakelock`, `ScreenBrightness`, `HapticFeedback`,
  `ShakeDetector`, sensors) must drop its last reference on unmount/screen-switch
  (or call `unregister_services()`), otherwise the registry — and the Dart side —
  accumulate dead services. The M0 spike hit the sibling of this bug class (the
  `@ft.component` renderer-context construction failure, roadmap §M1 owner
  requirement 1); the same discipline (construct services once, in the controller,
  not in render paths) applies.
- `Service.__post_init__` at `services/service.py:39`; `browser_context_menu.py:21`
  shows the two-arg `(self, ref)` post-init form.

### 3.8 `dart_bridge` transport (`app.py:216-330`, `427-530`; `messaging/flet_dart_bridge_server.py` 293 lines)

- Desktop/dev path: `is_embedded()` false → socket server (`__run_socket_server`,
  `app.py:390`; `FLET_SERVER_UDS_PATH` honoured at `app.py:411`) or web serving.
- Embedded path (Android/iOS): `is_embedded()` true (`platform_utils.py:70-77`)
  → `view` forced into `[FLET_APP, FLET_APP_HIDDEN, None]` (`app.py:216`) and, when
  `FLET_DART_BRIDGE_PORT` is set (`app.py:267`), the in-process `dart_bridge` byte
  channel (`__run_dart_bridge_server`, `app.py:488`) provided by `libdart_bridge`
  from `flet-dev/serious-python` (`app.py:263-264` comment). No socket accept loop;
  `blocking=is_embedded()` (`app.py:279`) and restart-aware waiting (`app.py:326`).
- **Process reuse** (`app.py:427-486`): `_DartBridgeServerHandle` — *"On Android
  process reuse (libdart_bridge stays loaded, the Dart VM restarts with fresh native
  port numbers), this handle replaces the underlying connection in place via
  `_swap_to_port`"* (`app.py:431-436` docstring). `_swap_to_port` closes the old
  conn and starts a new one under `_swap_lock`; `close()` drains in-flight swaps.
- `FletDartBridgeServer(Connection)` (`flet_dart_bridge_server.py:58`):
  `__init__` (:69), `start` (:92), `__on_bytes` (:103), `__inbound_loop` (:111),
  `__on_message` (:151), `send_message` (:221), `data_channel_for` (:239),
  `close` (:258). Socket twin `FletSocketServer` (`flet_socket_server.py:39`):
  `start` (:84), `handle_connection` (:129), receive/send loops (:251/:312),
  `__on_message` (:343), `send_message` (:425), `send_data_channel_frame` (:447),
  `data_channel_for` (:463), `unregister_data_channel` (:477), `close` (:480).

### 3.9 `flet run` dev storage, upload, assets

- `DEFAULT_ASSETS_DIR = "assets"` (`app.py:33`); `__get_assets_dir_path` /
  `__get_upload_dir_path` resolve relative-to-CWD; runtime override
  `FLET_ASSETS_DIR` (`app.py:728`; *"always set on purpose"*, `app.py:692`).
- `page.get_upload_url(file_name, expires)` (`page.py:1172`) → presigned URL for
  the built-in upload storage (M3 install flow could accept a user-picked rootfs
  tarball via `FilePicker` → upload URL → app storage, no extra HTTP server).

### 3.10 Lazy-loading semantics for extension authors (flet-terminal relevance)

`__getattr__` caching (`__init__.py:1821-1835`) means `import flet` is O(1)-ish and
each control module (e.g. `flet.controls.services.storage_paths`) loads on first
`ft.StoragePaths` touch. Our `services/` layer should mirror this: lazy-import
`proot_distro` (roadmap M3 already mandates the lazy gate) and lazy-touch
`flet_terminal` behind the platform-availability placeholder (roadmap §1b).

### 3.11 Error types (`controls/exceptions.py`)

- `FletException(Exception)` (:9) — base.
- `FletUnsupportedPlatformException(FletException)` (:21) — raised by
  `get_platform()`/`get_arch()` on unknown host, and by every `StoragePaths`
  method on web.
- `FletUnimplementedPlatformException(FletUnsupportedPlatformException)` (:27).
- `FletPageDisconnectedException(FletException)` (:33).
- Validation errors: `ValidationDeclarationError(RuntimeError)`
  (`utils/validation.py:65`); deprecation warnings via `utils/deprecated.py`
  (`deprecated` :54, `deprecated_class` :92, `deprecated_warning` :141).

---

## 4. How this project uses flet today (spike + milestones)

### 4.1 M0 spike — verified call sites (`m0-spike/src/main.py`)

| Call | Spike line | flet API (§3 ref) |
|---|---|---|
| `page.appbar = ft.AppBar(adaptive=True, title="M0 Spike")` | :357 | §3.2 |
| `page.scroll = ft.ScrollMode.AUTO` | :359 | §3.4 |
| `ft.Text(value="", font_family="Courier New", size=11, color=TERMINAL_TEXT, selectable=True)` | :376 | §3.2 |
| `ft.Column(controls=[log_text], scroll=ft.ScrollMode.AUTO, expand=True)` | :377 | §3.2 |
| `ft.Container(..., border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)))` | :378–382 | §2.7 note B |
| `ft.Button(label, on_click=_click)` helper `gate_button` | :499–503 | §3.2 |
| `ft.Button("Run ALL (G1-G4)", on_click=run_all, icon=ft.Icons.PLAY_ARROW)` | :560 | §3.2/§3.4 |
| `ft.Row([...])`, `ft.Divider()` | :559–578 | §3.2 |
| `ft.Text(..., weight=ft.FontWeight.BOLD)`, `color=ft.Colors.GREY_600` | :556–558 | §3.4 |
| `ft.Container(mt, height=280, border=ft.Border.all(1, ft.Colors.GREY_400))` | :576 | §3.2 |
| `isinstance(mt, ft.Text)` fallback when `flet-terminal` import fails | :452 | placeholder-pane pattern (roadmap §1b) |
| `def main(page: ft.Page)` + `ft.run` entry (implied by `flet run` dev loop) | :356 | §2.1 |

Device-resolved facts feeding the reference: Python-side PTY wins (O-3 CLOSED —
`pty.openpty` + `Popen` + `TIOCSWINSZ` ran on-device, spike-5); `sys.executable` is
the Flutter host so the CLI-subprocess route is dead; `MobileTerminal` must
construct outside component trees (renderer-context bug → M1 owner requirement 1).

### 4.2 Fullest-utilization proposals, tied to M3–M6

**M3 — scaffold + distro manager.**
- `@ft.observable AppState` + hooks (`use_state`, `use_context` +
  `ControllerMethodsCtx`) per roadmap; `Router` + `TemplateRoute` for
  distro-detail deep links (`/distro/<name>`).
- `services/proot_service.py` owns: `SharedPreferences` (install registry +
  settings), `StoragePaths` (rootfs homes), `Connectivity` (gate OCI pulls on
  `WIFI`, expose `on_change` to pause/resume), `FilePicker.pick_files/save_file`
  (import/export rootfs tarballs; `get_directory_path` for custom storage root),
  `UrlLauncher.launch_url` (docs/links), `Clipboard.set/get` (copy login argv,
  export report), `Share.share_files` (G6-style report export from UI).
- Install progress: `page.run_task` for the `asyncio.to_thread` install worker;
  `ProgressRing`/`ProgressBar` indeterminate + stage `Text`; `SnackBar` for
  completion; `HapticFeedback.selection_click` on gate pass; `ScreenBrightness`
  or `Wakelock` during multi-hundred-MB downloads (with refcount discipline §3.7).
- Probe-gating UI: `Banner` (proot missing), `AlertDialog` (first-run storage
  consent), `BottomSheet` (distro actions), `NavigationDrawer` (certified catalog
  + custom ref + settings).

**M4 — terminal integration.**
- Keep `MobileTerminal` construction outside `@ft.component` trees (M1 fix); wrap
  it in a `Pagelet` with an `AppBar` (session title + actions) — `Pagelet` exists
  precisely for this embedding.
- Session chrome: `IconButton`s (kill, resize-fit, extra-keys toggle),
  `PopupMenuButton` (send signal, paste, export scrollback via `Share`),
  `TabBar`/`Tabs` for multiple concurrent sessions (one `ProotSession` per tab,
  shaped like `ColabTerminalClient`: `send_input/set_size/on_stdout/alive/close`).
-.stdin prompts: `use_dialog` + `AlertDialog` with a `TextField` (CollabShell
  `stdin_hook.py` pattern), no `threading.Event` on the UI thread — bridge via
  `page.run_task`.
- Structured mode: `ListView` append-only outputs (`outputs_rev` cache),
  `Markdown` for rendered docs/help, `SelectionArea` around output blocks,
  `DataTable` for `iter_cached_images`/container inventory.
- `Page.pubsub` fan-out for multi-view (session on phone + monitor view);
  `DataChannel` reserved for future binary streaming (e.g. file transfer
  inside sessions) — client support is Dart-version-gated, keep behind a probe.
- Foreground-service notification stays NO by default (roadmap M4); if Play
  demands it, `flet-notifications` + its patcher is an M4-plan-mode decision.

**M5 — packaging/CI.** `flet build apk --split-per-abi` + AAB per roadmap;
`[tool.flet.cleanup]` may drop `oauthlib/**` (only `Page.login()` needs it —
we ship no login flow) but audit against the real tree, never sibling globs;
`FLET_ANDROID_SIGNING_*` secrets only via env; `FLET_CACHE_DIR` +
`PYTHON_BUILD_RELEASE_DATE` pinned; template ref follows the 1.0.4 pin
(untrusted `--template` never).

**M6 — policy.** `Markdown` + `ListView` licenses screen (proot GPL-2.0,
libtalloc GPL-3.0, proot-distro GPL-3.0-only + source links); `AboutDialog`
equivalent via `AlertDialog`; trademark-safe naming in `AppBar` titles.

---

## 5. How flet makes our app significantly better than Termux's proot-distro

Termux ships `proot-distro` as a **shell**: a terminal emulator + package scripts.
A shell can start processes; it cannot give you any of the following. Every item
names the concrete flet API (with section) that delivers it:

1. **A real UI toolkit, not escape codes.** 110+ typed widgets (§2.5) with
   dataclass constructors, validation (`V.*`), and adaptive
   material/cupertino rendering — distro cards, install wizards, settings
   screens, drawers, tabs, dialogs (§3.2). Termux renders text; we render an app.
2. **Declarative components.** `@ft.component` + `Renderer` + 8 hooks (§2.8)
   turn the AppShell, installer flow, and session tabs into pure functions of
   `@ft.observable` state — testable without a device (FakePage + contract
   tests), where Termux UI logic would be untestable shell glue.
3. **Device services as Python calls.** Sensors, battery, connectivity,
   clipboard, share sheet, file picker, haptics, wake-lock, brightness,
   app-storage paths — 21 services (§2.6) with zero JNI/Dart written by us.
   Termux exposes almost none of these to a proot session.
4. **Cross-platform from one codebase.** `AppView`/`PagePlatform`/`AdaptiveControl`
   (§2.1/§3.5/§5): the same code runs on Android (product), desktop
   (`flet run` UI loop), and web (docs/demos) — Termux is Android-only by design.
5. **Monetization path.** `flet-ads` (AdMob) plugs into the layout we already
   reserve (roadmap §1b/M4); a shell has no ad inventory.
6. **Storage APIs with platform semantics.** `StoragePaths` + `FLET_APP_STORAGE_*`
   (§3.6): cache vs documents vs support vs temp, created automatically,
   Play-policy-correct — versus Termux's single `$PREFIX` playground.
7. **A versioned client protocol, not a pty scrape.** msgpack `MessageAction`
   patches + `Session` index + refcount-pruned service registry (§2.9/§3.7):
   the UI is a live object tree, so install progress, session lists, and
   multi-view stay consistent without polling shell output.
8. **Routing and deep links.** `Router` + `TemplateRoute` (§2.8): shareable
   `/distro/<name>` routes, back-stack `View`s — a shell has one screen.
9. **Testability.** `Tester` + `Finder` + `pytest_plugin` (§2.12): scripted
   tap/enter-text/screenshot tests with golden support; Termux flows can only be
   tested by hand on-device.
10. **Auth, pubsub, data channels, uploads.** OAuth login flow (§2.10), cross-view
    `PubSubHub` (§2.9), binary `DataChannel`s, presigned `get_upload_url`
    (§3.9) — the import/export, multi-view, and future sync features have
    first-class primitives instead of `curl` in a guest.

Net: Termux gives us the *engine* (proot); flet gives us everything that makes it
a *product* — UI, state, services, storage, distribution, and tests — in pure
Python, with the device truth still gated by CI-built APKs per D-005.

---

## 6. Android/mobile notes

- **Embedded transport.** `is_embedded()` = `FLET_PLATFORM is not None`
  (`platform_utils.py:70-77`); Android sets `FLET_PLATFORM=android`
  (`platform_utils.py:60-67`). Embedded ⇒ socket server skipped; `dart_bridge`
  byte channel when `FLET_DART_BRIDGE_PORT` set (`app.py:216-269`); blocking run
  + restart-aware waiting (`app.py:279-330`).
- **Process reuse.** `libdart_bridge` stays loaded while the Dart VM restarts with
  fresh native ports; `_DartBridgeServerHandle._swap_to_port` swaps connections
  in place under `_swap_lock` (`app.py:427-486`). Sessions must therefore tolerate
  connection replacement — keep session state in Python (`SessionStore`,
  observables), never in connection handles.
- **Platform detection at runtime.** `page.platform: PagePlatform | None`
  (`page.py:595`); `is_android()/is_ios()/is_mobile()` (`platform_utils.py:50-88`);
  `page.web/pyodide/test` flags (`page.py:516-563`) for gating extension panes.
- **Storage.** §3.6; on Android these resolve into app-private dirs — the M3 home
  for rootfs/OCI layers/manifests. `get_external_storage_directories` may return
  `None` (scoped-storage devices) — always null-check before offering
  SD-card installs.
- **Known constraints (from source, all verified above).**
  1. `flet run` (desktop prebuilt client) contains no third-party extension Dart —
     `flet-terminal`/`flet-ads` never render locally (roadmap §1b; consistent with
     `Tester`/`flet_test_app` covering core widgets only).
  2. `StoragePaths` methods raise `FletUnsupportedPlatformException` on web —
     gate with `page.web`.
  3. `get_platform()`/`get_arch()` raise on mobile (empty host strings) —
     never call them on-device; use `page.platform` / `FLET_PLATFORM`.
  4. `PYTHON_BUILD_RELEASE_DATE`, `FLET_CACHE_DIR`, signing secrets: CI-only
     concerns (roadmap M5); no in-app effect.
  5. Sensors/location-style services stream events (`on_reading`) — each active
     subscription holds a registry entry (§3.7); stop streams when screens hide
     to save battery (the refcount rule is also a power rule).

---

## 7. Verification — file:line index + unverified items

`SP = C:\Users\nwoki\.zcode\workspace\default\proot-distro-flet\.venv\Lib\site-packages\flet\`.
All `SP/...` paths below were read; all signatures marked *(live)* came from
`inspect.signature` via the venv python; enum members marked *(live)* from
member iteration.

| Claim | Reference |
|---|---|
| Version 1.0.4 / Flutter 3.44.8 | `version.py:19` / `version.py:29` |
| License Apache-2.0; requires-python ≥3.10; runtime deps | `flet-1.0.4.dist-info/METADATA` (`License-Expression`, `Requires-Python`, `Requires-Dist`) |
| Pure wheel py3-none-any | `flet-1.0.4.dist-info/WHEEL` |
| 279 `.py`, 27 dirs, ~3.2 MB (+bytecode after import) | `find`/`du` (two runs; delta explained) |
| 538 exports; `_LAZY`; `__getattr__` cache; TYPE_CHECKING-only block | `__init__.py:738` / `:1280` / `:1821-1835` / top-of-file |
| `run` / `run_async` full signatures + defaults | *(live)* + `app.py:68-80` / `:150-161` |
| `AppView` / `WebRenderer` / `RouteUrlStrategy` members | *(live)* + `types.py:22` / `:49` / `:90` |
| `ServiceRegistry`, `register_service`, snapshot/restore, `__was_sent`, `unregister_services` refcount rule, `__internal_update` | `page.py:92,102,107,120,154,215,228,249` |
| `BasePage` fields + methods | `base_page.py:136,159-280,320-850` (spot lines in §2.2) |
| `Page` fields + methods incl. `login`/`logout`/`run_task`/`run_thread`/`navigate`/`get_upload_url` | `page.py:483,492-714,736-1355` (spot lines in §2.2) |
| Page event classes + `KeyboardEvent`/`LoginEvent` fields | `page.py:266-477` |
| `@control` overloads; `BaseControl`; `Control`; `LayoutControl` fields | `base_control.py:62-136,186-570`; `control.py` (whole file); `layout_control.py:33-310` |
| `Border.all/symmetric/only` = `@classmethod` | `border.py:204,230,257` (source read: `@classmethod` at :203/:229) |
| `Margin/Padding/BorderRadius.all` classmethods | `margin.py:35-36`; `padding.py:38-39`; `border_radius.py:40-41` |
| Every material/core/cupertino widget ↔ module | `@control("Name")` grep per module (§2.5 table) + `__all__` membership *(live)* |
| All 21 services: class, fields, methods | `services/*.py` lines in §2.6 table; method lines via `grep -n` per file |
| `StoragePaths` 10 methods + 4 env mirrors | `storage_paths.py:20-210` |
| `Component`/`Renderer`/`component`/`observable`/`memo`/hooks/router | `components/*.py` + `hooks/*.py` lines in §2.8; hook sigs *(live)* |
| Protocol: 7 `MessageAction`s, bodies; `Session`; servers; `SessionStore` | `protocol.py:231-474`; `session.py:38-693`; `flet_dart_bridge_server.py:58-258`; `flet_socket_server.py:39-480`; `session_store.py:6-71` |
| `DataChannel` ABC + 2 impls | `data_channel.py:54-143` |
| `PubSubHub` + `PubSubClient` full method lists | `pubsub_hub.py:15-258`; `pubsub_client.py:9-99` |
| Auth classes + providers; `Page.login/logout` | `auth/*.py`; `page.py:1193-1301` |
| Utils: 22 modules, entry points | per-module `grep -nP` (§2.11) |
| types.py 34 classes; `ScrollMode`/`FontWeight` members; `PagePlatform` helpers | `types.py` (1745 lines); members *(live)*; `PagePlatform` at `types.py:804` |
| `Colors` 399 / `Icons` 8825 / `CupertinoIcons` 1322 / `CupertinoColors` 95 attrs | *(live)* `len([a for a in dir(...)])` |
| `Theme` + 39 theme classes | `theme.py` class lines (§2.7) |
| `Duration`, exceptions (4), `Tester`/`Finder`, `pytest_plugin`, `security` fns, `platform_utils` fns, `device_info` classes, `events.py` classes, `Ref`/`QueryString`, `Window`, `MultiView`, `View`, `FLET_*` env vars | lines cited inline in §§2–6 |
| M0 spike call sites | `m0-spike/src/main.py:356-579` (spot lines in §4.1) |

**Unverified / explicitly bounded:**
- **U-1.** Exact constructor signatures of ~100 widgets are NOT all pasted here
  (only leading params + counts for the top-used ones). They are one
  `inspect.signature(ft.X.__init__)` call away each — omitted for size, not
  uncertainty. The `Button` full signature (§3.2) demonstrates the pattern.
- **U-2.** `canvas/__init__.py` and `fastapi/__init__.py` contents were listed
  but not read line-by-line; treated as re-export shims only.
- **U-3.** The exact env mirror for `get_application_support_directory` was not
  confirmed in the docstring excerpt read — use the async method (verified) rather
  than assuming a variable name.
- **U-4.** `page.push_route` (referenced by `navigate`'s docstring) was not
  independently located; `navigate(route, **kwargs)` itself is verified.
- **U-5.** File sizes/counts reflect the Windows venv install; Linux/macOS wheels
  of the same version are identical pure-Python payloads by construction
  (`py3-none-any`), but this was not re-measured there.
- **U-6.** Behavioural claims about the Dart client (rendering, `did_mount`
  delivery guarantees) are Python-side protocol readings only; device truth comes
  from CI APK runs per D-005.
