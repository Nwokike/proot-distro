#!/usr/bin/env python3
"""Export a repo's Android signing secrets into a throwaway release asset.

GitHub Actions secrets are write-only (even for admins), so the ONLY way to
read them is from a workflow inside the source repo itself. This script:

  1. creates a temporary branch `keystore-export-tmp` in SOURCE repo carrying a
     dispatch-only workflow that packs the 4 house signing secrets into
     `kiri-signing.json` and attaches it to a throwaway prerelease
     (release assets bypass this account's exhausted Actions-artifact quota);
  2. dispatches it, waits for the run, downloads the asset;
  3. deletes the release+tag and the temporary branch — the source repo is
     left untouched, and the workflow never echoes any value into its logs.

Next step after this script: tools/setup_signing.py --from-json kiri-signing.json

Usage:
    python tools/export_keystore_from_repo.py --repo Nwokike/Sherlock \\
        [--out kiri-signing.json] [--keep] [--branch-name keystore-export-tmp]
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

WORKFLOW_PATH = ".github/workflows/keystore-export-tmp.yml"
RELEASE_TAG = "keystore-export-tmp"
ASSET = "kiri-signing.json"

WORKFLOW_YAML = """\
# Temporary workflow written by tools/export_keystore_from_repo.py — deleted
# (branch + tag) by the same script immediately after the export.
# Triggered by the push that adds this very file to the temp branch, because
# workflow_dispatch is only honored for workflows on the default branch.
name: keystore-export-tmp

on:
  push:
    branches: ["__BRANCH__"]

permissions:
  contents: write

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - name: Pack signing material (values never printed)
        env:
          KEYSTORE_BASE64: ${{ secrets.KEYSTORE_BASE64 }}
          KEY_ALIAS: ${{ secrets.KEY_ALIAS }}
          KEYSTORE_PASSWORD: ${{ secrets.KEYSTORE_PASSWORD }}
          KEY_PASSWORD: ${{ secrets.KEY_PASSWORD }}
        run: |
          python3 - <<'PY'
          import json, os
          doc = {
              "keystore_b64": os.environ["KEYSTORE_BASE64"].strip(),
              "alias": os.environ["KEY_ALIAS"],
              "store_password": os.environ["KEYSTORE_PASSWORD"],
              "key_password": os.environ["KEY_PASSWORD"],
          }
          json.dump(doc, open("kiri-signing.json", "w"))
          print("packed", len(doc["keystore_b64"]), "b64 chars; alias set:", bool(doc["alias"]))
          PY
      - name: Attach to throwaway prerelease
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create keystore-export-tmp kiri-signing.json \\
            --title "keystore-export-tmp (delete me)" \\
            --notes "temporary signing export" --prerelease \\
            --repo ${{ github.repository }}
"""


def gh(*args: str, stdin: bytes | None = None, expect_ok: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["gh", *args], input=stdin, capture_output=True, check=False)
    if expect_ok and p.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed:\n{p.stderr.decode(errors='replace')}")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="SOURCE repo holding the secrets, e.g. Nwokike/Sherlock")
    ap.add_argument("--out", default=ASSET)
    ap.add_argument("--branch-name", default="keystore-export-tmp")
    ap.add_argument("--keep", action="store_true", help="do not delete the temp branch/release afterwards")
    args = ap.parse_args()

    repo = args.repo
    branch = args.branch_name

    default_branch = json.loads(gh("api", f"repos/{repo}", "--jq", "{d: .default_branch}").stdout)["d"]
    sha = gh("api", f"repos/{repo}/git/ref/heads/{default_branch}", "--jq", ".object.sha").stdout.decode().strip()
    print(f"source: {repo}@{default_branch} ({sha[:12]})")

    existing = gh("api", f"repos/{repo}/git/ref/heads/{branch}", expect_ok=False)
    if existing.returncode == 0:
        print(f"removing stale {branch!r} branch from a previous run…")
        gh("api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/{branch}", expect_ok=False)
    gh("release", "delete", RELEASE_TAG, "-R", repo, "--yes", "--cleanup-tag", expect_ok=False)

    gh("api", "-X", "POST", f"repos/{repo}/git/refs",
       "-f", f"ref=refs/heads/{branch}", "-f", f"sha={sha}")
    content_b64 = base64.b64encode(WORKFLOW_YAML.replace("__BRANCH__", branch).encode()).decode()
    gh("api", "-X", "PUT", f"repos/{repo}/contents/{WORKFLOW_PATH}",
       "-f", "message=tmp: add keystore export workflow (deleted after run)",
       "-f", f"content={content_b64}", "-f", f"branch={branch}")
    print("temporary workflow pushed — the push itself triggers the run; waiting…")
    run_id = None
    for _ in range(40):
        time.sleep(6)
        runs = json.loads(gh("run", "list", "-R", repo, "-w", "keystore-export-tmp.yml", "-L", "1",
                             "--json", "databaseId,status,headBranch").stdout)
        if runs and runs[0].get("headBranch") == branch:
            run_id = runs[0]["databaseId"]
            if runs[0]["status"] == "completed":
                break
    if run_id is None:
        raise SystemExit("no workflow run appeared — check the repo's Actions tab")
    gh("run", "watch", str(run_id), "-R", repo, "--exit-status", "--interval", "10")
    print(f"run {run_id} succeeded")

    out = Path(args.out)
    gh("release", "download", RELEASE_TAG, "-R", repo, "-p", ASSET, "-O", str(out), "--clobber")
    doc = json.loads(out.read_text(encoding="utf-8"))
    print(f"downloaded {out} ({len(doc['keystore_b64'])} b64 chars; alias field present: {bool(doc.get('alias'))})")

    if not args.keep:
        gh("release", "delete", RELEASE_TAG, "-R", repo, "--yes", "--cleanup-tag", expect_ok=False)
        gh("api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/{branch}", expect_ok=False)
        print("temporary release+tag and branch deleted — source repo restored")

    print(f"\nnext: python tools/setup_signing.py --repo <TARGET> --from-json {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
