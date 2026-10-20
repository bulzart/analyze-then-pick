#!/usr/bin/env python3
"""Install /analyze-then-pick into a Claude Code home (default ~/.claude).

What it does, in order:
  1. copies claude/commands, claude/skills/atp-* and claude/analyze-then-pick into the Claude home, rewriting the
     absolute paths of the machine the pipeline was built on (C:/Users/Glaresquare1/...) to this machine's paths
     (home, Python interpreter, CapCut draft store); everything else is copied byte for byte;
  2. installs the CapCut MCP server (vendor/capcut-mcp) at <claude home>/analyze-stack/tools/mcp/capcut-mcp and runs npm install;
  3. registers the MCP servers `higgsfield` and `capcut` at user scope with `claude mcp add` (skipped when already there);
  4. installs the Python packages and capcut-cli 0.25.0 (skip with --no-deps);
  5. checks the tools (ffmpeg, ffprobe, node, capcut, the CapCut template draft) and runs docs_tool.py check.

An existing install is never overwritten silently: without --force the installer stops; with --force the old files
are moved to ~/.claude-atp-backup-<stamp>/ and the old runs/ folder is carried over into the new install.
Standard library only, Python 3.10+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC = REPO / "claude"
BUILD_HOME = "C:/Users/Glaresquare1"
BUILD_PYTHON = "C:/Users/Glaresquare1/AppData/Local/Programs/Python/Python312/python.exe"
BUILD_CAPCUT = "C:/Users/Glaresquare1/AppData/Local/CapCut"
BUILD_DRAFTS = BUILD_CAPCUT + "/User Data/Projects/com.lveditor.draft"
TEMPLATE_DRAFT = "_analyze-stack-template"
HIGGSFIELD_MCP_URL = "https://mcp.higgsfield.ai/mcp"
CAPCUT_CLI = "capcut-cli@0.25.0"
KEEP_ON_REINSTALL = ("runs", "caught_flags.html")


def say(msg=""):
    print(msg, flush=True)


def fwd(p) -> str:
    return str(p).replace("\\", "/")


def default_capcut_root() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "CapCut"
    if platform.system() == "Darwin":
        return Path.home() / "Movies" / "CapCut"
    return Path.home() / ".local" / "share" / "CapCut"


def replacements(home: Path, python: str, capcut_root: Path, drafts: Path) -> list[tuple[bytes, bytes]]:
    """Longest first, so the specific paths win over the bare home prefix."""
    h = fwd(home)
    hb = str(home).replace("/", "\\")
    pairs = [
        (BUILD_PYTHON, fwd(python)),
        (BUILD_DRAFTS, fwd(drafts)),
        (BUILD_CAPCUT, fwd(capcut_root)),
        (BUILD_HOME, h),
        (BUILD_HOME.replace("/", "\\\\"), hb.replace("\\", "\\\\")),   # JSON-escaped examples in the docs
        (BUILD_HOME.replace("/", "\\"), hb),
    ]
    return [(a.encode(), b.encode()) for a, b in pairs]


def rewrite(data: bytes, pairs) -> bytes:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return data                       # binary: copied as is
    # two passes through placeholders, so a new path is never rewritten again by a shorter rule
    for i, (a, _) in enumerate(pairs):
        data = data.replace(a, b"\x00ATP%d\x00" % i)
    for i, (_, b) in enumerate(pairs):
        data = data.replace(b"\x00ATP%d\x00" % i, b)
    return data


def copy_tree(src: Path, dst: Path, pairs, dry: bool) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        if p.is_dir() or "__pycache__" in p.parts:
            continue
        out = dst / p.relative_to(src)
        n += 1
        if dry:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(rewrite(p.read_bytes(), pairs))
    return n


def run(cmd, **kw) -> subprocess.CompletedProcess:
    exe = shutil.which(cmd[0])
    if exe:
        cmd = [exe] + list(cmd[1:])
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claude-home", default=str(Path.home() / ".claude"), help="Claude Code home (default ~/.claude)")
    ap.add_argument("--python", default=sys.executable, help="Python the pipeline runs (default: the one running this)")
    ap.add_argument("--capcut-root", default=None, help="CapCut data folder (default: the platform's standard place)")
    ap.add_argument("--capcut-drafts", default=None, help="CapCut draft store (default: <capcut root>/User Data/Projects/com.lveditor.draft)")
    ap.add_argument("--force", action="store_true", help="replace an existing install (old files are moved to a backup folder)")
    ap.add_argument("--no-deps", action="store_true", help="skip pip / npm installs")
    ap.add_argument("--no-mcp", action="store_true", help="skip installing and registering the MCP servers")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    a = ap.parse_args()

    if not (Path(a.python).is_file() or shutil.which(a.python)):
        say(f"--python {a.python}: no such interpreter")
        return 2
    home = Path.home()
    ch =Path(a.claude_home).expanduser().resolve()
    capcut_root = Path(a.capcut_root).expanduser() if a.capcut_root else default_capcut_root()
    drafts = Path(a.capcut_drafts).expanduser() if a.capcut_drafts else capcut_root / "User Data" / "Projects" / "com.lveditor.draft"
    pairs = replacements(home, a.python, capcut_root, drafts)
    dry = a.dry_run

    say(f"Claude home     {ch}")
    say(f"Python          {fwd(a.python)}")
    say(f"CapCut drafts   {fwd(drafts)}")
    say()

    # 1. the pipeline -------------------------------------------------------------------------------------------
    targets = [ch / "commands" / "analyze-then-pick.md", ch / "analyze-then-pick"]
    targets += [ch / "skills" / d.name for d in sorted((SRC / "skills").iterdir()) if d.is_dir()]
    existing = [t for t in targets if t.exists()]
    kept = {}
    if existing:
        if not a.force:
            say("An install already exists here:")
            for t in existing:
                say(f"  {t}")
            say("Re-run with --force to replace it (the old files go to a backup folder; runs/ is carried over).")
            return 1
        backup = home / f".claude-atp-backup-{dt.datetime.now():%Y%m%d-%H%M%S}"
        say(f"Moving the existing install to {backup}")
        for t in existing:
            dest = backup / t.relative_to(ch)
            if not dry:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(t), str(dest))
            if t.name == "analyze-then-pick" and t.parent == ch:
                for k in KEEP_ON_REINSTALL:
                    if (dest / k).exists() or dry:
                        kept[k] = dest / k

    n = copy_tree(SRC / "commands", ch / "commands", pairs, dry)
    n += copy_tree(SRC / "skills", ch / "skills", pairs, dry)
    n += copy_tree(SRC / "analyze-then-pick", ch / "analyze-then-pick", pairs, dry)
    for k, src in kept.items():
        if not dry and src.exists():
            shutil.move(str(src), str(ch / "analyze-then-pick" / k))
            say(f"Carried over {k} from the old install")
    atp = ch / "analyze-then-pick"
    if not dry:
        (atp / "runs").mkdir(exist_ok=True)
        if not (atp / "caught_flags.html").exists():      # the flag record starts empty (run data is not in the repo)
            subprocess.run([a.python, str(atp / "scripts" / "atp.py"), "caught-flag", "render"], capture_output=True, text=True)
    say(f"Installed {n} files: the /analyze-then-pick command, {len(list((SRC / 'skills').iterdir()))} atp-* skills and the library")

    # 2-3. MCP servers ------------------------------------------------------------------------------------------
    mcp_dir = ch / "analyze-stack" / "tools" / "mcp" / "capcut-mcp"
    if not a.no_mcp:
        if mcp_dir.exists():
            say(f"CapCut MCP already present at {mcp_dir} (left as is)")
        else:
            say(f"Installing the CapCut MCP server at {mcp_dir}")
            if not dry:
                shutil.copytree(REPO / "vendor" / "capcut-mcp", mcp_dir, ignore=shutil.ignore_patterns("node_modules"))
        if not (mcp_dir / "node_modules").exists() and not dry:
            if shutil.which("npm"):
                r = run(["npm", "install", "--omit=dev"], cwd=str(mcp_dir))
                say("  npm install: " + ("ok" if r.returncode == 0 else "FAILED\n" + r.stderr[-1500:]))
            else:
                say("  npm not found: install Node.js 18+, then run `npm install` in that folder")

        if shutil.which("claude"):
            servers = {
                "higgsfield": ["claude", "mcp", "add", "--scope", "user", "--transport", "http", "higgsfield", HIGGSFIELD_MCP_URL],
                "capcut": ["claude", "mcp", "add", "--scope", "user", "capcut",
                           "-e", f"CAPCUT_DRAFTS_DIR={drafts}", "-e", f"CAPCUT_TEMPLATE_DRAFT={TEMPLATE_DRAFT}",
                           "--", "node", fwd(mcp_dir / "src" / "server.js")],
            }
            for name, cmd in servers.items():
                if run(["claude", "mcp", "get", name]).returncode == 0:
                    say(f"MCP server `{name}` already registered (left as is)")
                    continue
                if dry:
                    say(f"would run: {' '.join(cmd)}")
                    continue
                r = run(cmd)
                say(f"Registered MCP server `{name}`" if r.returncode == 0 else f"`{name}` registration FAILED: {r.stderr.strip()[-500:]}")
        else:
            say("`claude` is not on PATH: register the MCP servers yourself (README, section Install)")

    # 4. dependencies -------------------------------------------------------------------------------------------
    if not a.no_deps and not dry:
        say("Installing Python packages (requirements.txt)")
        r = subprocess.run([a.python, "-m", "pip", "install", "-q", "-r", str(REPO / "requirements.txt")], capture_output=True, text=True)
        say("  pip: " + ("ok" if r.returncode == 0 else "FAILED\n" + r.stderr[-1500:]))
        say("  optional (speech-to-text, OCR, audio analysis): pip install -r requirements-optional.txt")
        if not shutil.which("capcut"):
            if shutil.which("npm"):
                r = run(["npm", "install", "-g", CAPCUT_CLI])
                say(f"  npm -g {CAPCUT_CLI}: " + ("ok" if r.returncode == 0 else "FAILED\n" + r.stderr[-1500:]))
            else:
                say(f"  npm not found: install Node.js, then `npm install -g {CAPCUT_CLI}`")

    # 5. checks -------------------------------------------------------------------------------------------------
    say()
    say("Checks")
    for tool in ("ffmpeg", "ffprobe", "node", "capcut", "claude"):
        say(f"  {tool:8} {'found' if shutil.which(tool) else 'MISSING'}")
    say(f"  CapCut template draft {TEMPLATE_DRAFT}: {'found' if (drafts / TEMPLATE_DRAFT).exists() else 'MISSING (README, section The CapCut template draft)'}")
    if not dry:
        env = dict(os.environ)
        r = subprocess.run([a.python, str(ch / "analyze-then-pick" / "scripts" / "docs_tool.py"), "check"],
                           capture_output=True, text=True, env=env)
        tail = (r.stdout or r.stderr).strip().splitlines()[-3:]
        say("  docs_tool.py check: " + " | ".join(tail))
    say()
    say("Done. In Claude Code: /mcp to sign in to Higgsfield, then /analyze-then-pick")
    return 0


if __name__ == "__main__":
    sys.exit(main())
