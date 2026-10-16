# Compliance reference — Linux distro images (runtime OCI pulls + guest package archives)

**Date verified:** 2026-10-16 · **Scope:** M3 image-catalog defaults, M4/M5 UI copy, M6 store review
**Read first:** `docs/roadmap.md` (§M3 distro catalog, §M6 policy), `docs/reference/dep-proot-distro.md` (pull/install plumbing)

**How this app consumes distros (why this doc exists):** the app ships no rootfs
(except possibly one bundled offline fallback, M3) and pulls Linux distro images
**at runtime on user devices** from Docker Hub via upstream `proot-distro`
(`helpers/docker/pull.py::pull_image`, urllib, cached under `oci_layers/` /
`oci_manifests/`). `apt`/`apk` installs then run **inside the guest** against the
distro's own package archives. Certified set (roadmap §1): `ubuntu:24.04`,
`debian:bookworm`, `alpine:3.21`. Later: arbitrary user-supplied OCI refs.

**Citation rule used throughout:** every claim quoted from a primary source
(distro license/trademark/policy pages, Docker Hub ToS + pull-rate-limit docs,
Debian/Ubuntu/Alpine archive policies) carries its URL. Anything that could not
be verified against a primary source on 2026-10-16 is labeled **UNVERIFIED**.
Fetches were made 2026-10-16; policies change — re-verify at M6.

---

## 1. Per-image licensing & redistribution

### 1.1 Summary table

| Image | Contents license | Redistribution of the image | Trademark posture | App impact |
|---|---|---|---|---|
| **Ubuntu** (`ubuntu:24.04`) | Mixed per-package; overwhelmingly free/open-source. The image is built from official rootfs tarballs provided by Canonical (see §1.2). No single image-wide license statement found on the official image doc — **UNVERIFIED** as a blanket claim; per-package licenses apply | **Yes, unmodified**, expressly including VM/container-style images. Modified + still called "Ubuntu" needs Canonical approval/certification | Canonical owns UBUNTU et al. Do not use the marks in the app's own title/branding; nominative reference ("runs Ubuntu 24.04") is the permitted pattern | Lowest friction. Refer to "Ubuntu" factually; no Ubuntu logo in app icon/screens; keep images unmodified |
| **Debian** (`debian:bookworm`) | "composed primarily of free and open-source software, most of which is under the GNU GPL" (image doc). Social Contract: the Debian system stays 100% DFSG-free; others may ship Debian+other works **with no fee** | **Yes.** Explicitly: "We will allow others to create distributions containing both the Debian system and other works, without any fee from us" | SPI-owned mark, permissive nominative-use policy, but: no use in product/company names or domains; must carry SPI attribution + non-affiliation disclaimer | Lowest friction alongside Ubuntu. Add the SPI attribution line (copy in §1.3) |
| **Alpine** (`alpine:3.21`) | Per-package. Verified anchors: musl libc is **MIT**; BusyBox is **GPLv2** (SFC-enforced, source-offer obligation). No single Alpine-image license page found (alpinelinux.org/license 404s) — **UNVERIFIED** as a blanket claim | **Yes** in practice (MIT core + GPLv2 BusyBox with source availability via upstream); no Alpine redistribution prohibition found — but the absence of a published redistribution statement is itself **UNVERIFIED**, recheck at M6 | No Alpine trademark policy page found on 2026-10-16 — **UNVERIFIED**. Do not use any Alpine logo/markup in the app until checked | Fine technically; keep trademark use to plain-text factual reference |
| Kali (custom-ref path) | Debian-based; OffSec publishes official `kalilinux/kali-rolling` Docker images with usage docs | Pulling the official image at runtime is the documented consumption path | **OffSec-owned marks, permission-gated.** "KALI LINUX ™ is a trademark of OffSec"; no marks in domain names; commercial merch needs written permission | Factual text reference only; never imply the app is by/offiliated with OffSec/Kali |
| Arch (custom-ref path) | Per-package (pacman repos); Arch publishes official OCI images incl. on quay.io + ghcr.io | **Yes**, incl. via non-Docker-Hub official registries | Remix rule: only minimal/insubstantial derivatives may use the marks, non-commercially, clearly labeled as not-Arch; otherwise say "derived from Arch Linux" | Factual reference only ("Arch Linux container"); never brand |
| Fedora (custom-ref path) | Per-package (RPM repos); official image built in the Fedora Build System from a kickstart | **Yes**, incl. via Fedora's own `registry.fedoraproject.org` — **but** trademark conditions attach (next column) | **Strictest of the set.** Even *unmodified* Fedora software in new combinations needs Fedora Council approval to carry the marks; modified/virtual-image combos must drop `fedora-logos`, `fedora-release`, `fedora-release-notes` RPMs, use only the "Fedora Remix" secondary mark, and display a non-affiliation notice + link | Highest-risk mark. If Fedora is ever certified: nominative text use only, no logo, carry the non-affiliation notice; consider legal review before any Fedora-branded UI |

### 1.2 Notes per distro (quoted)

**Ubuntu — redistribution + trademark.**
Canonical's IP policy (https://canonical.com/legal/intellectual-property-policy —
note: `ubuntu.com/legal/...` now 302-redirects to `canonical.com/legal/...`):

> "You can redistribute Ubuntu in its unmodified form, complete with the
> installer images and packages provided by Canonical (this includes the
> publication or launch of virtual machine images). Any redistribution of
> modified versions of Ubuntu must be approved, certified or provided by
> Canonical if you are going to associate it with the Trademarks. Otherwise you
> must remove and replace the Trademarks and will need to recompile the source
> code to create your own binaries. This does not affect your rights under any
> open source licence applicable to any of the components of Ubuntu."

On marks (same page): Canonical's Trademarks "include: UBUNTU KUBUNTU EDUBUNTU
XUBUNTU JUJU LANDSCAPE"; "You cannot use the Trademarks in software titles. If
you are producing software for use with or on Ubuntu you may reference Ubuntu,
but must avoid: (i) any implication of endorsement, or (ii) any attempt to
unfairly or confusingly capitalise on the goodwill of Canonical or Ubuntu."

Why this is comfortable for us: **we do not redistribute Ubuntu at all** — the
user's device downloads Canonical's own published artifact from Docker Hub at
runtime. The official image doc
(https://github.com/docker-library/docs/blob/master/ubuntu/content.md, the
source of https://hub.docker.com/_/ubuntu) confirms provenance: "This image is
built from official rootfs tarballs provided by Canonical (see `dist-*` tags
at https://git.launchpad.net/cloud-images/+oci/ubuntu-base)"; `ubuntu:latest`
tracks the latest LTS. What we must still do: (a) never name/brand the app with
"Ubuntu" or use its logo; (b) keep the pulled image unmodified (we do — pulls
are verbatim upstream layers); (c) use factual-reference copy only (§5 UI
wording). Whether a *bundled offline fallback rootfs* (M3 exit criteria) counts
as "redistribution … in unmodified form" is covered by the quoted clause, but
confirm the exact bundling mechanic (full tarball vs re-packed layers) at M6 —
**UNVERIFIED** for re-packed artifacts.

**Debian — license/social contract + trademark.**
Official image doc
(https://github.com/docker-library/docs/blob/master/debian/content.md, source
of https://hub.docker.com/_/debian): "Debian is an operating system which is
composed primarily of free and open-source software, most of which is under the
GNU General Public License"; images are the "minbase" variant built
reproducibly with `debuerreotype`, default mirror `deb.debian.org`, EOL
releases served via the `debian/eol` image from `archive.debian.org`.
Debian Social Contract v1.2 (https://www.debian.org/social_contract): "Debian
will remain 100% free … We will allow others to create distributions containing
both the Debian system and other works, without any fee from us. In furtherance
of these goals, we will provide an integrated system of high-quality materials
with no legal restrictions that would prevent such uses of the system."
Debian Trademark Policy v2.0, published 19 January 2013
(https://www.debian.org/trademark; mark owned by Software in the Public
Interest, Inc., US-registered since 1999): permitted without asking — "true
factual statements about Debian", truthful compatibility statements
("nominative fair use"), describing Debian in articles/titles/posts; forbidden
without permission — any suggestion of affiliation/endorsement, use "in a
company or organization name or as the name of a product or service", use "in a
domain name", confusingly similar names. Mandatory handling: "Acknowledge
Software in the Public Interest, Inc.'s ownership of the Debian trademark
prominently", e.g. "[TRADEMARK] is a … trademark owned by Software in the
Public Interest, Inc.", plus a non-affiliation disclaimer ("X PROJECT is not
affiliated with Debian…"). Logos: never as part of your company/product logo.

**Alpine — license + (absent) trademark statement.**
About page (https://alpinelinux.org/about/): "Alpine Linux is an independent,
non-commercial, general purpose Linux distribution"; "built around musl libc
and busybox"; "A container requires no more than 8 MB"; "All userland binaries
are compiled as Position Independent Executables (PIE) with stack smashing
protection." Verified component licenses: musl is MIT —
https://git.musl-libc.org/cgit/musl/plain/COPYRIGHT ("musl as a whole is
licensed under the following standard MIT license … Copyright © 2005-2020 Rich
Felker, et al."); BusyBox is GPLv2 — https://busybox.net/license.html ("BusyBox
is licensed under the GNU General Public License version 2 … If you distribute
BusyBox without making the source code to the version you distribute available,
you violate the license terms" — enforcement via Software Freedom Conservancy).
Because we redistribute nothing (runtime pull only), the GPLv2 source-offer
duty does not trigger for us; it would matter only if we ever *shipped* a
BusyBox binary in the APK outside the guest image — flag for M2/M5 packaging
review. No Alpine trademark policy page and no image-wide license statement
could be located on 2026-10-16 (`https://alpinelinux.org/license` returns
404; the official image doc at
https://github.com/docker-library/docs/blob/master/alpine/content.md carries
no license section) — both **UNVERIFIED**; M6 action: recheck and, if still
absent, treat Alpine marks as do-not-use.

**Fedora — strictest mark (custom-ref path).**
Trademark guidelines as published on the Fedora wiki
(https://fedoraproject.org/wiki/Legal:Trademark_guidelines — page text notes it
holds the pre-2024 guidelines and points at
https://docs.fedoraproject.org/en-US/legal/trademarks/; both Fedora doc hosts
were behind bot-mitigation on 2026-10-16, so the quotations below are from the
wiki API which served the full text): "Fedora®, the Fedora word design, the
Infinity design logo, Fedora Remix, and the Fedora Remix word design … are
trademarks of Red Hat, Inc."; new combinations of *only* unmodified official-
repository software may carry the marks **only** "provided that … use of the
Fedora Trademarks is approved by the Fedora Council." For "virtual images or
appliances with combinations of Fedora software with non-Fedora or modified
Fedora software" the marks may **not** be used — only the "Fedora Remix"
Secondary Mark, "without prior permission", and only if "the fedora-logos,
fedora-release, and fedora-release-notes RPM packages are removed" plus "a
notice … indicating that … the software provided is not provided or supported
by the Fedora Project, and … official Fedora software is available through the
Fedora Project website". The current (post-2024) guidelines text could not be
fetched (bot-wall) — **UNVERIFIED** whether these clauses changed; recheck at
M6 before any Fedora certification. Official image provenance
(https://hub.docker.com/_/fedora): "generated in the Fedora Build System …
built from this kickstart file"; license tab uses Docker's generic per-image
wording ("it is the image user's responsibility to ensure that any use of this
image complies with any relevant licenses for all software contained within").

**Kali / OffSec brand (custom-ref path).**
Trademark policy (https://www.kali.org/docs/policy/trademark/, updated
2025-06-10): marks identify OffSec products; "use the trademarks in the exact
form as we use them (Kali Linux, Kali NetHunter & Kali NetHunter Pro)";
"first mention … should be accompanied by … ® or ™ … if in doubt, use ™";
"provide a statement … [trademark] is a trademark of OffSec", e.g. "KALI LINUX
™ is a trademark of OffSec"; "use of an OffSec trademark … in your domain names
is prohibited"; merch with marks only non-commercially for self/friends, never
on anything "you produce commercially … without receiving written permission".
Consumption path is documented and legitimate: official images at
`docker.io/kalilinux/kali-rolling` with usage docs at
https://www.kali.org/docs/containers/using-kali-docker-images/. Penetration-
testing-tool distribution policy and any Play-store-sensitive tooling notes were
not verified (the update-policies URL 404'd) — **UNVERIFIED**; if Kali is ever
certified, M6 must also review the Play "hacking tool" posture, not just the
mark. Note for copy: Kali is "part of OffSec's Community Projects".

**Arch (custom-ref path).**
Trademark Policy v2021-04-18 (https://wiki.archlinux.org/title/DeveloperWiki:TrademarkPolicy):
marks include "ARCHLINUX", "ARCH LINUX", "A simple, lightweight Linux
distribution" and the logo; "Remixes" (minimal configuration/artwork/package-
selection changes only; "removing or changing any infrastructure components …
will result in changes too large") may use the marks only non-commercially and
"in a way that makes it clear that your project … is not in fact Arch Linux";
anything more divergent "may not use the Trademarks … but … 'derived from Arch
Linux', 'based on Arch Linux', or 'a derivative of Arch Linux'". Arch is the
best-sourced non-Hub citizen: official OCI images ship weekly in the Docker Hub
library (`archlinux:latest`), daily at `docker.io/archlinux/archlinux`,
`quay.io/archlinux/archlinux`, and `ghcr.io/archlinux/archlinux`, cosign-
signed (https://github.com/archlinux/archlinux-docker README, fetched
2026-10-16); README also advises `pacman -Syu` right after starting a
container (rolling-release staleness — mirrors §4).

### 1.3 Required attribution copy (drop into the licenses screen, M6)

- Debian: "Debian is a registered trademark owned by Software in the Public Interest, Inc. This app is not affiliated with, endorsed by, or sponsored by the Debian project."
- Ubuntu: "Ubuntu and Canonical are registered trademarks of Canonical Ltd. This app is not affiliated with, endorsed by, or sponsored by Canonical." (Mark list per the IP policy; "not speaking for or on behalf of Canonical, no implied endorsement" pattern.)
- Alpine: plain-text factual reference only until a mark policy is found (**UNVERIFIED** — no logo use).
- Fedora (if ever listed): nominative text only + "This app is not provided or supported by the Fedora Project. Official Fedora software is available at https://fedoraproject.org/." (mirrors the Secondary-Mark notice requirement).
- Kali (if ever listed): first mention "KALI LINUX ™", footnote "KALI LINUX ™ is a trademark of OffSec."
- Arch (if ever listed): "derived from Arch Linux" phrasing; never present the container as Arch Linux itself.

---

## 2. Docker Hub Terms & rate limits

### 2.1 ToS clauses that touch this app (Docker Terms of Service, effective 2026-08-26 — date taken from the fetched page text "Effective as of: August 26, 2026"; https://www.docker.com/legal/docker-terms-service, fetched 2026-10-16)

1. **Automated pulls from devices are contemplated — and bind the user to the
   Terms.** "By accessing Docker Hub or downloading any Docker Image
   (including via the Docker CLI, the Docker Hub HTTP API, **or any automated
   tool**), you agree to be bound by these Terms as an Unauthenticated User."
   Our pull path (`proot-distro`'s urllib client hitting the registry API) is
   exactly "any automated tool". Consequence: the app's UI copy should not
   present Hub pulls as an ungoverned resource; the M4/M5 error strings must
   point at Docker's limits pages, not at us.
2. **Free access is rate-limited by reference.** "Free Hub Access is subject to
   the rate limits and usage restrictions posted at https://www.docker.com/pricing/
   and https://docs.docker.com/docker-hub/download-rate-limit/ (each
   incorporated by reference). Docker reserves the right to modify, restrict,
   or discontinue Free Hub Access at any time with or without notice."
   Limits can move without notice — the app must treat limit errors as normal,
   retryable-after-window UX, never as fatal.
3. **No scraping outside documented APIs/limits.** "You specifically agree not
   to … Use automated means (agents, robots, spiders, scrapers, or similar) to
   access the Website or Services **except as permitted by Docker (for example,
   through documented APIs and within published limits)**." We are compliant by
   construction (registry API, within limits) — do not add mirror-scraping,
   tag-list crawling, or aggressive retry loops.
4. **Redistribution permission is narrow — and we don't need it.** "users may
   redistribute Docker Images made available in Docker Hub at no cost, to third
   parties but **solely when bundled with or incorporated into its own software
   products, and not on a standalone basis**, and solely in accordance with
   these Terms." We do not redistribute images (each device pulls its own), so
   this clause is a non-issue — but it constrains the M3 offline-fallback
   design: if we ever *ship* a rootfs inside the APK/AAB or re-host layers on
   our own infra, that *is* redistribution/bundling and must be re-reviewed
   against this clause plus the distro clauses in §1.
5. **Enforcement.** "Docker may suspend or terminate your access … if Docker
   reasonably believes you have violated these Terms, used the Website or
   Services unlawfully, or created risk for Docker or others" (with prior
   notice + cure opportunity except where immediate suspension is needed).
   Per-device pulls cannot plausibly trip this; a shared backend
   proxy/mirror that aggregates pulls *could* — prefer no central pull proxy.

### 2.2 Current pull-rate-limit policy (date-stamped 2026-10-16; https://docs.docker.com/docker-hub/usage/ and https://docs.docker.com/docker-hub/usage/pulls/)

| User type | Limit per 6 hours | Basis |
|---|---|---|
| Unauthenticated | **100** | per IPv4 address or IPv6 /64 subnet |
| Personal (authenticated) | **200** | per account/namespace attribution |
| Pro / Team / Business (authenticated) | Unlimited | subject to fair use |

Quoted: "Unauthenticated and Docker Personal users are subject to a 6-hour
pull rate limit on Docker Hub." Mechanics that matter for us:

- **What counts:** "A pull for a normal image makes one pull for a single
  manifest"; multi-arch images count per architecture pulled. "Version checks
  do not count towards usage pricing" — a manifest HEAD that finds layers
  already cached is cheap. Our flow pulls one arch (arm64 on devices), so one
  fresh install ≈ a handful of pulls (manifest + per-layer blobs count as part
  of the pull transaction — exact blob-vs-manifest accounting is
  **UNVERIFIED**; budget conservatively).
- **Headers:** responses carry `ratelimit-limit: 100;w=21600` /
  `ratelimit-remaining: 20;w=21600` / `docker-ratelimit-source: <ip>` (example
  values from docs). `proot-distro` does not surface these today — M3 should log
  them on failure at minimum.
- **Limit vs abuse errors are distinguishable:** "The abuse limit returns a
  simple `429 Too Many Requests` response. The pull limit returns a longer
  error message that includes a link to documentation." The separate **abuse
  rate limit** applies "per IPv4 address or per IPv6 /64 subnet … in the order
  of thousands of requests per minute … applies to all users equally
  regardless of account level." UI copy must handle both.
- **Fair use backstop:** "excessive data transfer, pull rates, or data storage
  can lead to throttling, or additional charges. … we reserve the right to
  impose restrictions or apply additional charges."

### 2.3 What this means for mass user installs

Per-device pulls are **self-limiting**: each phone has its own IP/account
budget, installs happen at human frequency (a few pulls per install, rarely),
and layers cache on-device (`oci_layers/`). A fleet of 100k users does **not**
aggregate against one quota the way a CI farm would — each device is its own
quota subject. Realistic risk cases, in order:

1. **Carrier-grade NAT / shared egress** (many users behind few IPv4s):
   anonymous budgets are per-IP, so dense NAT pools could see limit errors
   sooner. Mitigation: optional authenticated pulls (§2.4), friendly retry
   copy.
2. **Re-pull storms**: reinstall loops, "reset container" wiping the layer
   cache, or a floating tag changing upstream and invalidating caches. Mitigate
   with digest-pinned certified defaults (§4) and by reusing `oci_layers/`
   across containers where upstream permits.
3. **Abuse-limit adjacency**: many devices on one office/campus IPv4 pulling
   simultaneously could brush the per-IP abuse limit (thousands/min — unlikely
   but possible at campus scale). Copy must say "wait and retry", never spin in
   a tight retry loop (also a ToS consideration per §2.1(3)).

### 2.4 Mitigation options

- **(Default) Per-device anonymous pulls.** No credentials, no account system,
  quota is the user's own. Keep this the default; it matches the roadmap (no
  login flow — `oauthlib` is even a cleanup-glob candidate).
- **Optional authenticated pulls.** `proot-distro` already supports
  `PD_DOCKER_AUTH` for private registries (dep-proot-distro.md §env contract);
  the same mechanism can carry a user's own Docker Hub token to lift them to
  the 200-pull Personal budget. M4/M5: a settings field "Docker Hub token
  (optional, raises pull limits)" + copy explaining tokens stay on-device.
  Never ship a shared baked-in token — that aggregates the whole fleet onto one
  quota and one suspendable identity.
- **Alternative registries (no single-vendor dependence).** Verified
  2026-10-16 (method: registry/API probes + official READMEs; Docker Hub
  library membership via hub.docker.com pages):
  - Arch: `quay.io/archlinux/archlinux`, `ghcr.io/archlinux/archlinux`
    (official, cosign-signed) — README-verified.
  - Fedora: `registry.fedoraproject.org` (probed HTTP 200 on `/v2/`) — official
    Fedora registry; image availability/tags **UNVERIFIED** beyond liveness.
  - Ubuntu: **mirror** endpoints verified live — `mirror.gcr.io`
    (`/v2/library/ubuntu/tags/list` returned full tag list incl. `24.04`,
    `noble`, `resolute`) and MCR `mcr.microsoft.com/mirror/docker/library/ubuntu`
    (tags `18.04`–`24.04` + `resolute`). Both are pull-through mirrors, not
    Canonical-run registries; Canonical-run OCI registry: **UNVERIFIED**.
  - Debian: no distro-run OCI registry verified — **UNVERIFIED**
    (`docker.debian.net` hosts checksums/tarballs, not OCI pulls).
  - Alpine: no distro-run OCI registry verified — **UNVERIFIED**.
  - Kali: `kalilinux/*` on Docker Hub is the documented source; other official
    registry endpoints **UNVERIFIED**.
  - Generic: `ghcr.io` / `quay.io` accept any OCI ref for the custom-image path
    (registry liveness probed: both return standard `UNAUTHORIZED` 401
    challenges on `/v2/`, i.e. live registries).
  - M3 catalog design should therefore carry a **per-distro registry field**
    (default Docker Hub; Arch/Fedora defaults can point at their official
    registries), not a single global registry constant.

---

## 3. Guest-side archive usage

After the rootfs lands, every `apt install` / `apk add` inside the guest hits
the *distro's* package infrastructure from the user's device. This is ordinary
client traffic — millions of Debian/Ubuntu/Alpine machines do exactly this —
but the UI and defaults should keep us good citizens.

### 3.1 What the archives are (verified 2026-10-16)

- **Debian:** `deb.debian.org` "provides mirrors" for `/debian/`,
  `/debian-debug/`, `/debian-ports/`, `/debian-security/` … "This service is
  sponsored by Fastly" (https://deb.debian.org/). The official Debian image
  uses it as default mirror
  (https://github.com/docker-library/docs/blob/master/debian/content.md).
  Debian's mirror docs govern *mirror operators* (ftpsync discipline,
  bandwidth commitments — https://www.debian.org/mirror/ftpmirror), not
  clients; **no published per-client rate policy found (UNVERIFIED whether one
  exists)**.
- **Ubuntu:** `archive.ubuntu.com` (releases) + `security.ubuntu.com`
  (security pocket). Liveness verified: `http://archive.ubuntu.com/ubuntu/dists/noble/Release`
  serves the Noble `Release` file (`Origin: Ubuntu … Suite: noble … Version:
  24.04`, arm64 included). The old wiki Mirrors page is now an empty
  migration stub (https://wiki.ubuntu.com/Mirrors) — **no published client
  acceptable-use statement found (UNVERIFIED)**.
- **Alpine:** `dl-cdn.alpinelinux.org` is the default CDN endpoint and is live
  (`APKINDEX.tar.gz` for v3.20/v3.21 aarch64 fetched HTTP 200 on 2026-10-16);
  the published mirror list at
  https://dl-cdn.alpinelinux.org/alpine/MIRRORS.txt names dozens of community
  mirrors (incl. `*.edge.kernel.org`). **No published client rate policy found
  (UNVERIFIED)**.

### 3.2 Acceptable-use behavior for a fleet of devices

Normal `apt update && apt install <pkg>` / `apk add <pkg>` traffic from many
devices is the archives' designed workload (every container, CI runner, and
phone-with-Termux does this). Nothing in the fetched policies suggests per-
client pull quotas for package downloads. That said, three behaviors deserve
deliberate product decisions:

1. **The optional "pre-upgrade everything" convenience.** Running a full
   `apt full-upgrade` / `apk upgrade -a` immediately after every install
   multiplies per-install bytes several-fold across the fleet with marginal
   user value (fresh certified images are days-to-weeks old, not years).
   Recommendation: default OFF; offer it as an explicit user action labeled
   "Update all guest packages (downloads ~hundreds of MB)"; never run it
   silently on first boot or on a timer.
2. **Refresh cadence.** `apt update` on every app launch or on a background
   schedule would be pure metadata churn with no user benefit. Refresh indexes
   only when the user opens the package flow (or explic
...[truncated 6154 chars]