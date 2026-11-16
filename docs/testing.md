# Testing 1.2.0

Manual test pass for the Android build. Work top to bottom; each item is
`action -> expected`. Tick the box when it behaves as written; note the device
and Android version at the end.

Device: ____________________  Android: ______  Build: 1.2.0 (build 4, fix 15)

---

## 1. Home and containers

- [ ] Fresh install, no containers: hero, "No containers yet" card, one banner, then Install/Search.
- [ ] Install Alpine from a popular tile: the confirm dialog appears, then progress; the container appears **above** the banner.
- [ ] Search Docker Hub with limit 25, 50 and 100. Results sit under the bar, one banner after every 5th result.
- [ ] A search with no hits shows exactly one banner.
- [ ] Install with a non-host architecture (for example `linux/amd64` on ARM). The container boots; emulated is slow but works.
- [ ] Container card menu: Rename, Backup snapshot (gzip and zstd), Restore, Copy a path, Sync folder, Browse files, Inspect, Run command, Reset, Remove, Apps on display.
- [ ] Fresh Alpine shell: `uname -a` runs with no `dbus-run-session: not found`.
- [ ] Arch hint: one line under the install bar reads "Host runs at full speed; other architectures use an emulator and may be slower."

## 2. Terminal

- [ ] Open a shell: the prompt renders and the extra keys work (ESC, TAB, CTRL, ALT, arrows).
- [ ] CTRL and ALT stay sticky for exactly one key.
- [ ] Menu: Clear, Copy full output, Search, Zoom, theme cycle. Pick Dracula.
- [ ] Settings shows Dracula under Terminal defaults after that change.
- [ ] Change theme, size (12) and blink off in Terminal defaults. A new shell uses all three.
- [ ] "Start X display" from a shell, then type `xterm` in that same shell. The window appears in the viewer and `echo $DISPLAY` is set.
- [ ] **Scaling parity**: the bare display from "Start X display" is letterboxed to fit the screen, same as an app display. No black bars that shouldn't be there.
- [ ] Shell with options: the user list comes from the container. `-u kiri` on Alpine answers "no user 'kiri' in alpine. It defines: ..." and no session starts.
- [ ] A missing work dir, a missing bind host and a non-executable emulator path each show a readable message and start nothing.

## 3. Display sheet

- [ ] Open display from a container card: ONE sheet opens with NO App | Desktop switch. Status line, Preset apps, command cell with OUTPUT panel, and Save as preset **under** the cell.
- [ ] Type `xterm` and press play. The display starts, OUTPUT streams, the viewer appears, Back returns to the app.
- [ ] "Install a desktop (experimental)" tile is collapsed by default. Tapping expands it to show the DE picker, the install cell, Start desktop, and Re-check container. Available whether or not a DE is already installed.
- [ ] Tap a saved preset: it starts with its saved work dir and env.
- [ ] Save a preset with a 60-character name twice: only one entry remains.
- [ ] Type in Run as / advanced, close and reopen the sheet: the text is still there.
- [ ] Pick display `:1` and start: the session key is `container:1`. Starting again answers "a display is already starting. Wait a moment".
- [ ] Fit "Fit the whole desktop" (default): portrait shows the whole desktop letterboxed. "Remote resize" and "Actual size" behave differently.
- [ ] LAN on shows a Wi-Fi URL. Tunnel on without ssh explains that desktop support installs openssh-client.
- [ ] Advanced: depth 16, fps 60, quality 50, view only, kick other viewers, audio rate 48 kHz, mic format s16le, viewer log debug. The stream reflects them (view only blocks input, debug fills the viewer console).

## 4. Display tab

- [ ] Section order: **Distros** (one card per container with Open display) comes FIRST; **Presets** comes LAST (it grows with installed apps).
- [ ] Presets card shows BOTH detected apps (from `.desktop` entries, with container name) AND manual presets. Installing `xterm` in a container, then opening the Display tab, shows it in the Presets list.
- [ ] Tap a detected app: it starts on the right container's display.
- [ ] A running display appears under Running with Open, Stop and the menu. Stop shows "stopping..." then the row disappears within 3 seconds (no lingering spinner).
- [ ] **Multi-display**: with `:0` running, tap "Open display" on the same container. The sheet opens (does NOT resume `:0`). Pick `:1` and start. Two displays run simultaneously; both appear under Running.
- [ ] **Kill**: Stop on `:0` kills it. Then "Open display" → sheet → start a new app. No "a display is already starting" error after the stop completes.
- [ ] `pkill Xvnc` from a shell: the row turns into Failed with a reason plus Retry and Dismiss.
- [ ] Reopen the app while the foreground service kept it alive: the running display is still listed.

## 5. Files

- [ ] Browse `/` and `/root`; upload a file, download it, zip a folder.
- [ ] Preview a text file in monospace and an image inline. A very large file shows a truncated preview (no hang).
- [ ] The filter is the house SearchBar and filters as you type.
- [ ] Copy and sync between container and host, with checksum on and off, and with prune.
- [ ] The FAB modal is fully contained: nothing overflows outside the dialog bounds.

## 6. Settings

- [ ] Theme Light, Dark and System switch instantly and persist.
- [ ] Display defaults work inline and persist across a reopen.
- [ ] Notifications shows Allowed or Blocked; Blocked opens Android settings.
- [ ] Privacy and Ads shows Personalized or Non-personalized; the privacy form opens where required. Ads still serve in both states.
- [ ] Running processes lists sessions with "N guest process(es), signal:", a signal pill, per-row stop and Stop all.
- [ ] Build and push: the architecture list matches the app's derived list (host reads `host (aarch64)` on a 64-bit phone).
- [ ] Environment Probe shows passed or check; tapping opens the detail.
- [ ] Default environment: add `FOO=bar` and Save; a new shell prints it with `echo $FOO`. `1BAD` shows the invalid-key message.
- [ ] Debugging output shows the last 20 lines, Copy works, Clear empties it, Full log opens the dialog.
- [ ] Storage shows the total with "containers X · OCI cache Y"; tapping opens the layout; cached images show real sizes or "size unavailable"; Sweep, Clear build cache, Clear app cache and Clear all cache each confirm first.
- [ ] Narrow screen or split view: Terminal defaults, Notifications, Privacy, Running processes, Storage rows, the Default environment Manage button and the About rows all drop **under** the title.
- [ ] About: one icon; the version row opens release notes; Contact, Rate, More apps and Source open externally; Diagnostics opens in the app; license texts come before the Python list; Privacy and Terms open; Exit confirms.

## 7. Background and lifecycle

- [ ] Start a display, press Home and wait two minutes. The notification persists and the display is still running on return.
- [ ] Exit from the notification stops shells and displays.
- [ ] Rotate portrait to landscape and back; the keyboard never covers the prompt.

## 8. Updates

- [ ] About shows "Version 1.2.0 · build 4 · Flet 1.1.2", or "Update available · tap to view" when the feed is ahead.
- [ ] The GitHub release for the tag carries the changelog bullets as a proper Markdown list.

## 9. Display viewer (noVNC)

- [ ] **Two-finger drag** scrolls inside the guest app (Chrome page, terminal, file manager).
- [ ] **One finger** drags the mouse (click-drag, text selection). This is upstream noVNC's design, not a bug.
- [ ] **Mic button** in the toolbar: tap to turn on (icon turns green, snack confirms), tap again to turn off. The PulseAudio mic module loads and unloads.
- [ ] Toolbar order: Back, Title, Terminal, Mic, Fullscreen, More.

## 10. Desktop install

- [ ] XFCE on Alpine: install completes and the desktop renders with icons (no Wnck crash from the missing pixbuf cache).
- [ ] MATE on Alpine: works (was already confirmed).
- [ ] LXQt on Alpine: installs and renders (heavier than XFCE/MATE but functional).
- [ ] XFCE on Ubuntu: `apt upgrade` completes without the glibc "Kernel must be upgraded" error.
- [ ] Desktop install holds the wakelock: minimizing the app during install does not kill the install.
- [ ] Experimental marker visible on the install tile in the sheet.

## 11. Storage housekeeping

- [ ] Download a file, share it, then open Settings → Storage → the layout: no growing pile of orphan exports (the staged copy is removed after hand-off).
- [ ] Storage shows "Clear app cache" beside the OCI actions; tapping it reports how many probe entries and temp files it removed.
- [ ] Start and stop a display a few times, reopen the app: old display-log generations are pruned (at most three per container, nothing older than a week), and the newest log of a failed display is still readable from its Logs button.

## 12. Regressions

- [ ] Every button uses the compact house pill.
- [ ] Every search is the glass SearchBar, never a boxed input.
- [ ] Cold start: open the app and go straight to Display. Cards show readiness instantly instead of "probing..." (the 1-hour probe cache).
- [ ] Leave the app open for a minute: no error spam in Debugging output.
- [ ] All em dashes removed from user-visible text (labels, snacks, tooltips).
