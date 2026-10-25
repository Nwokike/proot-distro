<p align="center">
  <img src="src/assets/icon.svg" alt="Proot Distro" width="320" />
</p>

<p align="center">
  Proot Distro — Run rootless Linux containers, interactive terminals & manage files natively on Android
</p>

<p align="center">
  <a href="https://play.google.com/store/apps/details?id=ng.kiri.prootdistro"><img src="https://img.shields.io/badge/Google_Play-Android-3DDC84?style=for-the-badge&logo=google-play&logoColor=white" alt="Google Play Store" /></a>
  <a href="https://github.com/Nwokike/proot-distro/releases/latest"><img src="https://img.shields.io/badge/Download-APK-orange?style=for-the-badge&logo=android&logoColor=white" alt="Download APK" /></a>
  <img src="https://img.shields.io/badge/Built_with-Flet_1.0.4-00B0FF?style=for-the-badge&logo=flutter&logoColor=white" alt="Flet" />
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
</p>

---

## Download

| Platform | Download | Notes |
| :---: | :---: | :--- |
| 🤖 **Android** | [![Play Store](https://img.shields.io/badge/Google_Play-414141?style=flat-square&logo=google-play&logoColor=white)](https://play.google.com/store/apps/details?id=ng.kiri.prootdistro) | Recommended for Android mobile users |
| 📦 **Android (APK)** | [![Download APK](https://img.shields.io/badge/Download_APK-orange?style=flat-square&logo=android&logoColor=white)](https://github.com/Nwokike/proot-distro/releases/latest) | Direct APK download for sideloading |

### Android Architecture Build Splits

| Variant | Download | Notes |
| :--- | :---: | :--- |
| 📱 **ARM64** (most phones) | [**proot-distro-flet-arm64-v8a.apk**](https://github.com/Nwokike/proot-distro/releases/latest/download/proot-distro-flet-arm64-v8a.apk) | Modern 64-bit Android devices |
| 💻 **x86_64** (emulators) | [**proot-distro-flet-x86_64.apk**](https://github.com/Nwokike/proot-distro/releases/latest/download/proot-distro-flet-x86_64.apk) | Chromebooks & Android emulators |

---

## Core Capabilities

| Capability | Description |
| :--- | :--- |
| **Rootless Linux Userspace** | Execute genuine Linux distributions (Debian, Ubuntu, Alpine) on Android and Linux without root privileges or system modifications. |
| **Interactive PTY Terminal** | Real-time POSIX pseudo-terminal sessions with custom virtual extra keys, sticky modifiers (CTRL/ALT), search, zoom, and live title tracking. |
| **Tabbed Multi-Shell Workspace** | Seamlessly switch between concurrent container shells directly above the terminal canvas. |
| **Container Filesystem Explorer** | Browse container directories, preview text and images, upload files, download files, and zip entire directories with rootfs-jailed safety. |
| **Snapshot Backup & Restore** | Archive complete container filesystems to `.tar.gz` and restore them anywhere on your device via the native OS file picker. |
| **Docker Hub & OCI Integration** | Search Docker Hub for public container images and install with one tap or specify custom OCI image references. |
| **Directory Synchronization** | Fast host-to-container and container-to-container folder synchronization with optional checksum verification and destination pruning. |
| **Private & Sandboxed** | Operates strictly in private application storage. No user accounts, no telemetry, and zero remote tracking. |

---

## License & Compliance

Proot Distro incorporates open-source components under free software licenses, including PRoot (GPL-2.0-or-later), PRoot-Distro (GPL-3.0-only), talloc (GPL-3.0-or-later), and Flet (Apache-2.0).

Complete machine-readable Corresponding Source for all GPL components is available in accordance with GPL §6(b) at https://github.com/Nwokike/proot-distro. Full license texts are included in the repository's `LICENSES/` directory and in the app under **Settings → About → Open-Source Licenses**.
