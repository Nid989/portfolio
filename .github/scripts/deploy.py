#!/usr/bin/env python3
"""Deploy static site to Vercel via REST API (no CLI required)."""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ["VERCEL_TOKEN"]
PROJECT_ID = os.environ["VERCEL_PROJECT_ID"]
TEAM_ID = os.environ["VERCEL_ORG_ID"]
TARGET = "production" if os.environ.get("GITHUB_REF") == "refs/heads/main" else "preview"

API = "https://api.vercel.com"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

SKIP_DIRS = {".git", ".github", ".vercel", "handoff", "node_modules"}
SKIP_FILES = {".gitignore", ".DS_Store"}


def upload_file(path: str, content: bytes) -> dict:
    sha1 = hashlib.sha1(content).hexdigest()
    headers = {
        **AUTH,
        "Content-Length": str(len(content)),
        "x-now-digest": sha1,
        "Content-Type": "application/octet-stream",
    }
    req = urllib.request.Request(f"{API}/v2/files?teamId={TEAM_ID}", data=content, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            print(f"  uploaded {path}")
    except urllib.error.HTTPError as e:
        if e.code == 200:
            print(f"  cached   {path}")
        else:
            raise RuntimeError(f"Upload {path} failed: {e.code} {e.read()[:300]}")
    return {"file": path, "sha": sha1, "size": len(content)}


def collect_files(root: str) -> list[dict]:
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name in SKIP_FILES or name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            with open(full, "rb") as f:
                content = f.read()
            result.append(upload_file(rel, content))
    return result


def create_deployment(files: list[dict]) -> dict:
    body = json.dumps({
        "name": "portfolio",
        "projectId": PROJECT_ID,
        "target": TARGET,
        "files": files,
    }).encode()
    headers = {**AUTH, "Content-Type": "application/json"}
    req = urllib.request.Request(f"{API}/v13/deployments?teamId={TEAM_ID}", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Deployment failed: {e.code} {e.read()[:500]}")


def main():
    root = os.environ.get("GITHUB_WORKSPACE", ".")
    print(f"Target: {TARGET}")
    print("Uploading files...")
    files = collect_files(root)
    print(f"Creating deployment ({len(files)} files)...")
    result = create_deployment(files)
    url = result.get("url", "unknown")
    state = result.get("readyState", result.get("status", "unknown"))
    print(f"URL:    https://{url}")
    print(f"State:  {state}")
    if state in ("ERROR", "CANCELED"):
        print(json.dumps(result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
