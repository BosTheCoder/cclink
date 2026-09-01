#!/usr/bin/env python3
"""Turn a Claude Code session id into a link, and a link back into a session.

Two halves of one round trip:

    ccl.py <id>            ->  https://cc.buildwithbos.com/#s=<id>   (paste in a note)
    ccl.py --resume <uri>  ->  cd <the session's cwd> && claude --resume <id>

The link carries nothing but a UUID, and the UUID is validated on both sides —
by the page before it redirects, and again here before anything touches a shell.
The browser is not trusted; neither is the registry.

`claude --resume` only finds a session when it runs from the directory the
session was in. The id is enough to recover that: the transcript lives at
~/.claude/projects/<mangled-cwd>/<id>.jsonl and records its own "cwd". The
directory name is not used for this — mangling replaces every "/" with "-",
which a path containing a real hyphen makes ambiguous to reverse.

Stdlib only. Shared with the page via fixtures.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_BASE = "https://cc.buildwithbos.com"
SCHEME = "ccode"
# Claude Code session ids are lowercase UUIDs. Anchored, and the only character
# class that reaches a command line: hex and hyphen. No quoting question can
# arise downstream because nothing else can get this far.
SESSION_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Cap the scan for "cwd": it sits in the first few lines (the opening
# last-prompt record has no cwd), and a long transcript is not worth reading.
CWD_SCAN_LINES = 200

# Exit code for a --resume that never got as far as running claude.
RESUME_FAILED = 78


class CclError(Exception):
    """Anything the user should see as a one-line message, not a traceback."""


def base_url() -> str:
    return os.environ.get("CCLINK_BASE", DEFAULT_BASE).rstrip("/")


def is_session_id(value: str) -> bool:
    return bool(SESSION_ID_RE.match(value))


def parse(value: str, base: str | None = None) -> str:
    """Extract a session id from an id, a ccode:// URI, or an https link.

    Raises CclError on anything else. This is the security boundary: every
    entry point goes through it before the id is used for a path or a command.
    """
    base = (base or base_url()).rstrip("/")
    raw = (value or "").strip().strip('"').strip("'")

    if raw.startswith(f"{SCHEME}://"):
        rest = raw[len(SCHEME) + 3 :]
        prefix = "resume/"
        if not rest.startswith(prefix):
            raise CclError(f"unsupported {SCHEME}:// action in {raw!r} (expected {SCHEME}://resume/<id>)")
        candidate = rest[len(prefix) :].rstrip("/")
    elif "://" in raw:
        if not raw.startswith(base + "/") and raw.rstrip("/") != base:
            raise CclError(f"link is not on {base}: {raw!r}")
        _, _, fragment = raw.partition("#")
        if not fragment.startswith("s="):
            raise CclError(f"link has no #s=<id> fragment: {raw!r}")
        candidate = fragment[2:]
    else:
        candidate = raw

    candidate = candidate.lower()
    if not is_session_id(candidate):
        raise CclError(f"not a Claude Code session id: {value!r}")
    return candidate


# Boundaries matter: without them a 37-hex run would yield its first 36
# characters, quietly linking to a different session than the one pasted.
LOOSE_ID_RE = re.compile(r"(?<![0-9a-fA-F-])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F-])")


def extract(text: str, base: str | None = None) -> str:
    """Lenient front door: pull the first UUID-shaped run out of free text, so a
    line copied straight from a note ("- `c --resume <id>`") works. The result
    still goes through parse(), so leniency here buys no leniency downstream."""
    raw = (text or "").strip()
    try:
        return parse(raw, base)
    except CclError:
        match = LOOSE_ID_RE.search(raw)
        if not match:
            raise
        return parse(match.group(0), base)


def link_for(session_id: str, base: str | None = None) -> str:
    """Build the shareable https link. The id rides in the fragment, which
    browsers never send to a server, so the host never learns what you opened."""
    return f"{(base or base_url()).rstrip('/')}/#s={parse(session_id, base)}"


def uri_for(session_id: str) -> str:
    return f"{SCHEME}://resume/{parse(session_id)}"


def projects_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECTS_DIR", Path.home() / ".claude" / "projects"))


def transcript_for(session_id: str, root: Path | None = None) -> Path:
    root = root or projects_dir()
    matches = sorted(root.glob(f"*/{parse(session_id)}.jsonl"))
    if not matches:
        raise CclError(
            f"no transcript for session {session_id} under {root}.\n"
            "It may belong to another machine, or predate this sync."
        )
    return matches[0]


def resolve_cwd(session_id: str, root: Path | None = None) -> Path:
    """The directory the session ran in, read out of its own transcript."""
    path = transcript_for(session_id, root)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for _, line in zip(range(CWD_SCAN_LINES), handle):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            cwd = record.get("cwd") if isinstance(record, dict) else None
            if cwd:
                return Path(cwd)
    raise CclError(f"{path} records no cwd in its first {CWD_SCAN_LINES} lines.")


def clipboard_read() -> str:
    for cmd in (["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"], ["pbpaste"]):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    # WSL: powershell is the reliable reader, and it appends a newline.
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, check=True,
        ).stdout
        return out.replace("\r\n", "\n")
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise CclError("nothing to read: no argument given and no clipboard tool found.")


def clipboard_write(text: str) -> None:
    for cmd in (["clip.exe"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["pbcopy"]):
        try:
            subprocess.run(cmd, input=text, text=True, check=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise CclError("no clipboard tool found (tried clip.exe, wl-copy, xclip, pbcopy).")


def cmd_resume(session_id: str) -> int:
    """Replace this process with claude, in the right directory."""
    cwd = resolve_cwd(session_id)
    if not cwd.is_dir():
        raise CclError(f"session {session_id} ran in {cwd}, which does not exist on this machine.")
    # Windows starts this through `wsl.exe -- ...`, which supplies a bare PATH
    # with none of the login shell's additions — so `claude` is typically not
    # findable here even though it is in an ordinary terminal. install.sh
    # records where it lives; CCODE_CLAUDE overrides for a one-off.
    exe = os.environ.get("CCODE_CLAUDE") or shutil.which("claude")
    if not exe:
        raise CclError(
            "cannot find the claude binary.\n"
            "Re-run windows/install.sh from a shell where `claude` works, "
            "or set CCODE_CLAUDE to its path."
        )

    print(f"==> {cwd}")
    print(f"==> claude --resume {session_id}")
    os.chdir(cwd)
    try:
        os.execv(exe, [exe, "--permission-mode", "auto", "--resume", session_id])
    except OSError as exc:
        raise CclError(f"could not run {exe}: {exc}")
    return 0  # unreachable; execv does not return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ccl",
        description="Claude Code session id <-> shareable link, and the resume launcher behind ccode://.",
    )
    parser.add_argument("value", nargs="?", help="session id, ccode:// URI, or cclink URL (default: clipboard)")
    parser.add_argument("-c", "--copy", action="store_true", help="copy the result to the clipboard")
    parser.add_argument("-u", "--uri", action="store_true", help="print the ccode:// URI instead of the https link")
    parser.add_argument("--resume", action="store_true", help="resolve and exec claude --resume (used by the ccode:// handler)")
    parser.add_argument("--cwd", action="store_true", help="print the session's directory and exit")
    parser.add_argument("--base", default=None, help=f"link base (env CCLINK_BASE, default {DEFAULT_BASE})")
    args = parser.parse_args(argv)

    try:
        if args.value is not None:
            raw = args.value
        elif not sys.stdin.isatty():
            # Piped: `cr --cmds -d yesterday | ccl`. extract() finds the id in
            # whatever line shape arrives.
            raw = sys.stdin.read()
        else:
            raw = clipboard_read()
        # --resume is fed by the URL handler and stays strict; everything else
        # is fed by a human pasting, and may be a whole line from a note.
        session_id = parse(raw, args.base) if args.resume else extract(raw, args.base)

        if args.resume:
            return cmd_resume(session_id)
        if args.cwd:
            print(resolve_cwd(session_id))
            return 0

        result = uri_for(session_id) if args.uri else link_for(session_id, args.base)
        print(result)
        if args.copy:
            clipboard_write(result)
            print("(copied)", file=sys.stderr)
        return 0
    except CclError as exc:
        print(f"ccl: {exc}", file=sys.stderr)
        # A distinct code for the resume path so the launcher can tell "I could
        # not start the session" (hold the tab open, the user needs to read it)
        # from "claude itself exited non-zero" (nothing to see, let it close).
        return RESUME_FAILED if args.resume else 1


if __name__ == "__main__":
    sys.exit(main())
