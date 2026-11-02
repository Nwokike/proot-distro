"""BuildView — `proot-distro build` (Dockerfile → OCI image) + `push`.

Every upstream build option is exposed: context path, -f/--file (incl. "-" for
stdin), -t/--tag (repeatable), --build-arg (repeatable), -a/--architecture,
--target stage, --emulator, -o/--output (repeatable), --install-as, --no-cache,
-v/--verbose. RUN steps execute under the bundled proot by upstream's build
engine; the stage lines stream live into the log card via state.build_logs.
After a successful build the result card offers `push` (ref, arch,
--allow-insecure) with PD_DOCKER_AUTH from Settings.

Layout follows the lm-router/Sherlock settings-form pattern: uppercase section
headers, glass cards with hairline dividers between rows, labeled fields,
`Row(wrap=True)` field groups (side-by-side on wide, under on narrow), Switch
for booleans, pill FilledButton action rows — all sizes from tokens.
"""

from __future__ import annotations

import re

import flet as ft

from components import card, pill_dropdown, section_header
from components.banner_ad import pooled_banner_ad
from core import theme, tokens
from core.state import state
from screens.settings_components import _setting_row, _settings_card
from state.controller_ctx import ControllerMethodsCtx

_ARCH_CHOICES = ("host", "aarch64", "arm", "i686", "riscv64", "x86_64")


def _field(
    label: str, value: str, on_change, *, multiline: bool = False, width: int | None = None
) -> ft.TextField:
    return ft.TextField(
        label=label,
        hint_text=label,
        value=value,
        on_change=lambda e: on_change(e.control.value),
        text_size=tokens.FONT_SM,
        multiline=multiline,
        min_lines=2 if multiline else None,
        max_lines=6 if multiline else None,
        expand=width is None,
        width=width,
        height=None if multiline else tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
    )


def _arch_dropdown(value: str, on_select):
    """Tiny pill dropdown (CollabShell model-pill style), not a big rectangle."""
    return pill_dropdown(
        "Arch (-a)",
        ft.Icons.MEMORY_ROUNDED,
        list(_ARCH_CHOICES),
        value,
        on_select,
        tooltip="Target CPU architecture (-a/--architecture; default: host)",
    )


def _switch(label: str, value: bool, on_change, tooltip: str = "") -> ft.Switch:
    return ft.Switch(
        label=label,
        value=value,
        on_change=lambda e: on_change(bool(e.control.value)),
        tooltip=tooltip or None,
    )


def _pill_button(
    label: str, icon: ft.IconData, on_click, *, disabled: bool = False
) -> ft.FilledButton:
    return ft.FilledButton(
        label,
        icon=icon,
        on_click=on_click,
        disabled=disabled,
        height=tokens.CONTROL_MD,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)),
    )


def _divider() -> ft.Divider:
    return ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border())


@ft.component
def BuildView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    # Sherlock breakpoint: on narrow screens every row's control goes UNDER
    # the label (stacked), never beside it.
    is_narrow = bool(page and getattr(page, "width", None) and page.width < 600)

    path_f, set_path = ft.use_state(".")
    dockerfile_f, set_dockerfile = ft.use_state("")
    tags_f, set_tags = ft.use_state("")
    buildargs_f, set_buildargs = ft.use_state("")
    arch_f, set_arch = ft.use_state("host")
    target_f, set_target = ft.use_state("")
    emulator_f, set_emulator = ft.use_state("")
    outputs_f, set_outputs = ft.use_state("")
    install_as_f, set_install_as = ft.use_state("")
    no_cache, set_no_cache = ft.use_state(False)
    verbose, set_verbose = ft.use_state(False)

    push_ref_f, set_push_ref = ft.use_state("")
    push_arch_f, set_push_arch = ft.use_state("host")
    push_insecure, set_push_insecure = ft.use_state(False)

    def _do_build(_e=None) -> None:
        if st.build_busy:
            return
        tags = [t for t in re.split(r"[,\s]+", tags_f.strip()) if t]
        build_args = [ln.strip() for ln in buildargs_f.splitlines() if ln.strip()]
        outputs = [ln.strip() for ln in outputs_f.splitlines() if ln.strip()]
        opts = {
            "path": path_f.strip() or ".",
            "dockerfile": dockerfile_f.strip() or None,
            "tags": tags or None,
            "build_args": build_args or None,
            "override_arch": None if arch_f == "host" else arch_f,
            "target_stage": target_f.strip() or None,
            "emulator": emulator_f.strip() or None,
            "outputs": outputs or None,
            "install_as": install_as_f.strip() or None,
            "no_cache": no_cache,
            "verbose": verbose,
        }
        page.run_task(methods.run_build, opts)

    def _do_push(_e=None) -> None:
        ref = push_ref_f.strip()
        if not ref and st.build_result and st.build_result.get("tags"):
            ref = st.build_result["tags"][0]
        if not ref:
            ref = tags_f.strip().split(",")[0].strip()
        if not ref:
            return
        page.run_task(
            methods.push_image, ref, "" if push_arch_f == "host" else push_arch_f, push_insecure
        )

    # Sherlock settings-card form: one _setting_row per option; on narrow
    # screens each trailing control stacks UNDER its label (stacked=is_narrow).
    form = _settings_card(
        [
            _setting_row(
                ft.Icons.FOLDER_OPEN_ROUNDED,
                "Build context path",
                "Directory with the Dockerfile; default '.'",
                _field("path", path_f, set_path, width=220),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.DESCRIPTION_ROUNDED,
                "Dockerfile (-f)",
                "'-' = stdin; blank = <path>/Dockerfile",
                _field("-f", dockerfile_f, set_dockerfile, width=220),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.LABEL_ROUNDED,
                "Tags (-t)",
                "Comma/space separated, repeatable",
                _field("tags", tags_f, set_tags, width=220),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.ARCHIVE_ROUNDED,
                "Target stage (--target)",
                "Multi-stage build stage name",
                _field("--target", target_f, set_target, width=tokens.FIELD_TARGET_WIDTH),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.MEMORY_ROUNDED,
                "Architecture (-a)",
                "Target CPU architecture; default: host",
                _arch_dropdown(arch_f, set_arch),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.UPLOAD_FILE_ROUNDED,
                "Outputs (-o)",
                "One output FILE per line",
                _field("-o", outputs_f, set_outputs, width=220),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.INSTALL_DESKTOP_ROUNDED,
                "Install as (--install-as)",
                "Also install the built image as a container",
                _field(
                    "--install-as",
                    install_as_f,
                    set_install_as,
                    width=tokens.FIELD_INSTALL_AS_WIDTH,
                ),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.COMPUTER_ROUNDED,
                "QEMU emulator (--emulator)",
                "PATH used for foreign-arch RUN steps",
                _field("--emulator", emulator_f, set_emulator, width=tokens.FIELD_EMULATOR_WIDTH),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.SETTINGS_APPLICATIONS_ROUNDED,
                "Build args (--build-arg)",
                "K=V, one per line",
                _field("--build-arg", buildargs_f, set_buildargs, width=260),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.BOLT_ROUNDED,
                "No cache (--no-cache)",
                "Ignore the build cache for this build",
                _switch("", no_cache, set_no_cache),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.TUNE_ROUNDED,
                "Verbose (-v)",
                "Stream full build logs",
                _switch("", verbose, set_verbose),
                stacked=is_narrow,
            ),
            _divider(),
            ft.Container(
                content=ft.Row(
                    controls=[
                        _pill_button(
                            "Build", ft.Icons.BUILD_ROUNDED, _do_build, disabled=st.build_busy
                        )
                    ],
                ),
                padding=ft.Padding(
                    tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD
                ),
            ),
        ]
    )

    log_card = None
    if st.build_busy or st.build_logs:
        log_card = card(
            ft.Column(
                controls=[
                    ft.Text(
                        st.build_stage or "building…",
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600,
                        color=theme.accent(),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    ln,
                                    font_family=tokens.MONO_FONT,
                                    size=tokens.FONT_XXS,
                                    color=theme.text_dim(),
                                )
                                for ln in st.build_logs[-60:]
                            ],
                            spacing=tokens.SPACE_NANO,
                            scroll=ft.ScrollMode.AUTO,
                            height=tokens.LOG_BOX_HEIGHT,
                        ),
                        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
                        border=ft.Border.all(tokens.HAIRLINE, theme.surface_alt()),
                        border_radius=tokens.RADIUS_SM,
                        padding=tokens.SPACE_SM,
                    ),
                ],
                spacing=tokens.SPACE_XS,
            )
        )

    result_card = None
    if st.build_result:
        tags_txt = ", ".join(st.build_result.get("tags") or []) or "(derived tag)"
        result_card = card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED, color=theme.ok(), size=tokens.ICON_MD
                            ),
                            ft.Text(
                                f"Built: {tags_txt}",
                                size=tokens.FONT_SM,
                                weight=ft.FontWeight.W_600,
                                color=theme.text(),
                                expand=True,
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                    ),
                    ft.Text(
                        (st.build_result.get("output") or "")[-800:],
                        size=tokens.FONT_XS,
                        color=theme.text_dim(),
                        selectable=True,
                    ),
                ],
                spacing=tokens.SPACE_XS,
            )
        )

    push_card = _settings_card(
        [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Push a built image to its registry",
                            size=tokens.FONT_MD,
                            weight=ft.FontWeight.W_600,
                            color=theme.text(),
                        ),
                        ft.Text(
                            "Uses PD_DOCKER_AUTH (Settings → Registry Authentication) for private repos.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                    ],
                    spacing=tokens.SPACE_XXS,
                ),
                padding=ft.Padding(
                    tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_SM
                ),
            ),
            _divider(),
            _setting_row(
                ft.Icons.LABEL_ROUNDED,
                "Image ref to push",
                "Defaults to the first build tag",
                _field("ref", push_ref_f, set_push_ref, width=240),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.MEMORY_ROUNDED,
                "Architecture (-a)",
                "Architecture the manifest was built for",
                _arch_dropdown(push_arch_f, set_push_arch),
                stacked=is_narrow,
            ),
            _divider(),
            _setting_row(
                ft.Icons.WARNING_AMBER_ROUNDED,
                "Allow insecure (--allow-insecure)",
                "Permit plain-HTTP / untrusted-TLS registries",
                _switch("", push_insecure, set_push_insecure),
                stacked=is_narrow,
            ),
            _divider(),
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                _pill_button(
                                    "Push",
                                    ft.Icons.CLOUD_UPLOAD_ROUNDED,
                                    _do_push,
                                    disabled=st.push_busy,
                                )
                            ],
                        ),
                        ft.Text(st.push_status, size=tokens.FONT_XS, color=theme.text_dim())
                        if st.push_status
                        else ft.Container(),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
                padding=ft.Padding(
                    tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD
                ),
            ),
        ]
    )

    controls: list[ft.Control] = [
        section_header("Build image"),
        form,
    ]
    if log_card is not None:
        controls.append(log_card)
    if result_card is not None:
        controls.append(result_card)
    controls.extend(
        [
            pooled_banner_ad("build-1", page),
            section_header("Push image"),
            push_card,
            ft.Container(height=tokens.NAV_BAR_CLEARANCE),
        ]
    )
    return ft.Column(
        controls=controls, spacing=tokens.SPACE_SM, expand=True, scroll=ft.ScrollMode.AUTO
    )
