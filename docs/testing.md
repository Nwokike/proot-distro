# Testing 1.2.1

Manual test pass for the Android build. Work top to bottom; each item is
`action -> expected`. Tick the box when it behaves as written; note the device
and Android version at the end.

Device: ____________________  Android: ______  Build: 1.2.1 (build 5)

---

## 1. Home and containers

- [ ] Fresh install, no containers: hero, "No containers yet" card, one banner, then Install/Search.
- [ ] Install Alpine from a popular tile: the confirm dialog appears, then progress; the container appears **above** the banner.
- [ ] The popular-distro list ends with one banner after Debian (before the install log area).
- [ ] Search Docker Hub with limit 25, 50 and 100. Results sit under the bar, one banner after every 5th result.
- [ ] A search with no hits shows exactly one banner.
- [ ] Install with a non-host architecture (for example `linux/amd64` on ARM). The container boots; emulated is slow but works.
- [ ] Container card menu: Rename, Backup snapshot (gzip and zstd), Restore, Copy a path, Sync folder, Browse files, Inspect, Run command, Reset, Remove, Apps on display.
- [ ] Fresh Alpine shell: `uname -a` runs with no `dbus-run-session: not found`.
- [ ] Arch test: in an Arch container, `pacman -Sy` completes (no seccomp or sandbox-user failure), and `pacman -S nano` then works.
- [ ] Arch hint: one line under the install bar reads "Host runs at full speed; other architectures use an emulator and may be slower."

## 2. Terminal

- [ ] Open a shell: the prompt renders and the extra keys work (ESC, TAB, CTRL, ALT, arrows).
- [ ] CTRL and ALT stay sticky for exactly one key.
- [ ] Menu: Clear, Copy full output, Search, Zoom, theme cycle. Pick Dracula.
- [ ] Settings shows Dracula under Terminal defaults after that change.
- [ ] **Theme default**: with the app in dark mode, a new shell starts with Dracula. Switch the app to light, the next shell starts with Colab Light. An explicitly chosen theme always wins.
- [ ] "Start X display" from a shell, then type `xterm` in that same shell. The window appears in the viewer and `echo $DISPLAY` is set.
- [ ] **Scaling parity**: the bare display from "Start X display" is letterboxed to fit the screen, same as an app display.
- [ ] Shell with options: the user list comes from the container. `-u kiri` on Alpine answers "no user 'kiri' in alpine. It defines: ..." and no session starts.
- [ ] A missing work dir, a missing bind host and a non-executable emulator path each show a readable message and start nothing.

## 3. Display sheet

- [ ] Open display from a container card: ONE sheet opens with NO App | Desktop switch and NO "Install a desktop" tile.
- [ ] Status line, Preset apps with a refresh button, this container's presets, the command cell, Save as preset under it, then the gesture hint.
- [ ] Type `xterm` and press play. The display starts, OUTPUT streams, the viewer appears, Back returns to the app.
- [ ] **Presets refresh**: install an app inside the container (for example `apk add xterm` in the shell), then open the sheet and tap refresh. The new app appears without restarting the app.
- [ ] **Container scope**: a preset saved for debian does not appear in the fedora sheet.
- [ ] **Sandbox checkbox**: a detected Chromium/Electron app row shows "no sandbox" checked; an xterm row shows it unchecked. Unchecking Chromium and starting it shows the sandbox error; checking it works.
- [ ] Save a preset with a 60-character name twice: only one entry remains.
- [ ] Type in Run as / advanced, close and reopen the sheet: the text is still there.
- [ ] Pick display `:1` and start: the session key is `container:1`. Starting again answers "a display is already starting. Wait a moment".
- [ ] LAN on shows a Wi-Fi URL. Tunnel on without ssh explains that the container needs openssh-client.

## 4. Display tab

- [ ] Section order: **Distros** (one card per container with Open display), one banner, then **Presets** LAST.
- [ ] Presets shows the detected apps of every container, each with its container name and the sandbox checkbox, plus the saved presets.
- [ ] **Refresh**: tap the refresh icon next to Presets; a spinner appears and an app installed meanwhile shows up.
- [ ] Tap a detected app: it starts on the right container's display.
- [ ] A running display appears under Running with Open, Stop and the menu. Stop shows "stopping..." then the row disappears within 3 seconds.
- [ ] **Multi-display**: with `:0` running, tap "Open display" on the same container. The sheet opens (does NOT resume `:0`). Pick `:1` and start. Two displays run simultaneously.
- [ ] **Kill**: Stop on `:0` kills it. Then start a new app immediately; no "a display is already starting" error.
- [ ] `pkill Xvnc` from a shell: the row turns into Failed with a reason plus Retry and Dismiss.
- [ ] Reopen the app while the foreground service kept it alive: the running display is still listed.

## 5. Files

- [ ] Browse `/` and `/root`; upload a file, download it, zip a folder.
- [ ] Preview a text file in monospace and an image inline. A very large file shows a truncated preview (no hang).
- [ ] Preview an executable script: the dialog shows three buttons (Run, Display, Terminal) and the file. Tap Run: the command cell opens with the file's folder as Working dir and output streams; Stop kills it.
- [ ] Preview a binary file (for example `/usr/bin/ls`): no garbage. A card shows the type and size, and the three run buttons are there.
- [ ] The filter is the house SearchBar and filters as you type.
- [ ] The banner sits at the very top and the file list reaches the bottom edge, with no dead space under the banner.
- [ ] The FAB modal is fully contained: nothing overflows outside the dialog bounds.

## 6. Settings

- [ ] Theme Light, Dark and System switch instantly and persist.
- [ ] Display defaults work inline and persist across a reopen.
- [ ] Advanced display options include "Forward guest notifications" (default on).
- [ ] Notifications shows Allowed or Blocked; Blocked opens Android settings.
- [ ] Privacy and Ads shows Personalized or Non-personalized; ads still serve in both states.
- [ ] Running processes lists sessions with "N guest process(es), signal:", a signal pill, per-row stop and Stop all.
- [ ] Build and push: the architecture list matches the app's derived list (host reads `host (aarch64)` on a 64-bit phone).
- [ ] Environment Probe shows passed or check; tapping opens the detail.
- [ ] Default environment: add `FOO=bar` and Save; a new shell prints it with `echo $FOO`.
- [ ] Debugging output shows the last 20 lines, Copy works, Clear empties it, Full log opens the dialog.
- [ ] Storage shows the total with "containers X · OCI cache Y"; Sweep, Clear build cache, Clear app cache and Clear all cache each confirm first.
- [ ] Narrow screen or split view: Terminal defaults, Notifications, Privacy, Running processes, Storage rows and the About rows all drop **under** the title.
- [ ] About: version row opens release notes; Contact, Rate, More apps and Source open externally; Diagnostics opens in the app; Privacy and Terms open; Exit confirms.

## 7. Background and lifecycle

- [ ] Start a display, press Home and wait two minutes. The notification persists and the display is still running on return.
- [ ] Exit from the notification stops shells and displays.
- [ ] **Notification tap**: with a display running in the background while you are in the Terminal tab, tap the persistent notification. The display comes to the front without leaving the terminal first.

## 8. Updates

- [ ] About shows "Version 1.2.1 · build 5 · Flet 1.1.2", or "Update available · tap to view" when the feed is ahead.
- [ ] The GitHub release for the tag carries the changelog bullets as a proper Markdown list.

## 9. Display viewer (noVNC)

- [ ] **Two-finger drag** scrolls inside the guest app. **One finger** drags the mouse. **Pinch** zooms.
- [ ] The gesture reminder appears once when the viewer opens.
- [ ] **Fullscreen keyboard**: enter fullscreen (orientation lock), open the on-screen keyboard. The keyboard covers the bottom of the viewer; the desktop keeps its size and does not shrink or jump.
- [ ] **System bars**: in fullscreen the status and navigation bars hide; leaving fullscreen brings them back.
- [ ] **Mic button**: the mic starts off. Tap it: Android asks for the microphone permission once; on Allow the snack says "microphone on". Tap again: "microphone off". If you deny, the snack says the permission was denied and the mic stays off.
- [ ] Toolbar order: Back, Title, Terminal, Mic, Fullscreen, More.

## 10. Share and the access code

- [ ] Share on a running display opens the dialog even with LAN and the tunnel both off: Local URL, access code and copy buttons are there.
- [ ] Copy the Local URL and open it in a browser on the phone: our sign-in page appears. Type the code: the viewer opens.
- [ ] A wrong code shows "That code is not correct" and the form again.
- [ ] LAN on: the Wi-Fi URL works from another device with the same code page.
- [ ] The "Share…" system sheet appears only when the public tunnel has a URL.

## 11. Guest notifications

- [ ] In a display, make a guest app raise a notification (for example a browser asking for permission). An Android notification appears with the app name and text.
- [ ] Turn "Forward guest notifications" off and repeat: no Android notification appears.

## 12. Regressions

- [ ] Every button uses the compact house pill; every toggle is the small switch.
- [ ] Every search is the glass SearchBar, never a boxed input.
- [ ] Banners: after the Home distro list, between Distros and Presets on the Display tab, and after every fifth preset. Never as the very last element.
- [ ] Cold start: open the app and go straight to Display. Cards show readiness instantly (the 1-hour probe cache).
- [ ] All em dashes removed from user-visible text.
- [ ] Play Console device support: the new build declares microphone, touchscreen and leanback as not required (no 18-device drop like 1.2.0).
