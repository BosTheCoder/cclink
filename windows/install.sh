#!/usr/bin/env bash
# Register the ccode:// URL scheme on Windows, from WSL. Re-runnable.
#
#   ./windows/install.sh            install / update
#   ./windows/install.sh --uninstall
#
# Writes to HKCU only, so it needs no administrator. It does not touch the
# claude:// scheme, which the Claude desktop app already owns — that collision
# is why this one is called ccode.
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(dirname "$HERE")"
LAUNCHER="$REPO/ccode-resume"
DISTRO="${WSL_DISTRO_NAME:-}"

die() { echo "install.sh: $*" >&2; exit 1; }

command -v reg.exe >/dev/null || die "reg.exe not found — this only runs inside WSL."
[ -n "$DISTRO" ] || die "WSL_DISTRO_NAME is unset; cannot tell Windows which distro to call back into."

WINHOME="$(wslpath "$(cmd.exe /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')")"
DEST="$WINHOME/cclink"
PS1_WSL="$DEST/ccode-open.ps1"

if [ "${1:-}" = "--uninstall" ]; then
  reg.exe delete 'HKCU\Software\Classes\ccode' /f >/dev/null 2>&1 || true
  rm -rf "$DEST"
  echo "Removed the ccode:// handler and $DEST."
  exit 0
fi

[ -x "$LAUNCHER" ] || die "$LAUNCHER is missing or not executable (chmod +x it)."

# Windows starts the launcher through `wsl.exe --`, which reads no shell config
# at all. Record the PATH of the shell running this script so the launcher can
# find claude (and anything else) the way an ordinary terminal would.
CLAUDE_BIN="$(command -v claude || true)"
[ -n "$CLAUDE_BIN" ] || die "claude is not on PATH here. Run this from a shell where it is."
cat > "$REPO/.ccode-env" <<ENV
# Written by windows/install.sh on $(date -Iseconds). Not tracked: machine-specific.
# Re-run install.sh after moving claude or changing PATH.
export PATH="$PATH"
export CCODE_CLAUDE="$CLAUDE_BIN"
ENV
echo "==> claude:    $CLAUDE_BIN"

echo "==> Distro:   $DISTRO"
echo "==> Launcher: $LAUNCHER"

# The handler script lives on the Windows side. Running it off \\wsl.localhost
# works until WSL is stopped, at which point clicking a link would silently
# start the VM or fail; a real local file has neither problem.
mkdir -p "$DEST"
sed -e "s|__DISTRO__|$DISTRO|g" -e "s|__LAUNCHER__|$LAUNCHER|g" \
    "$HERE/ccode-open.ps1.in" > "$PS1_WSL"

PS1_WIN="$(wslpath -w "$PS1_WSL")"
echo "==> Handler:  $PS1_WIN"

# .reg wants each backslash doubled.
PS1_REG="${PS1_WIN//\\/\\\\}"
REG_TMP="$(mktemp --suffix=.reg)"
trap 'rm -f "$REG_TMP"' EXIT

# UTF-16LE with a BOM: reg.exe import rejects a UTF-8 .reg with non-ASCII, and
# writing it in the encoding it wants costs nothing.
python3 - "$REG_TMP" "$PS1_REG" <<'PY'
import sys
path, ps1 = sys.argv[1], sys.argv[2]
cmd = f'powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File \\"{ps1}\\" -Uri \\"%1\\"'
body = f'''Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\\Software\\Classes\\ccode]
@="URL:Claude Code session"
"URL Protocol"=""

[HKEY_CURRENT_USER\\Software\\Classes\\ccode\\shell\\open\\command]
@="{cmd}"
'''
open(path, "w", encoding="utf-16-le").write("﻿" + body.replace("\n", "\r\n"))
PY

reg.exe import "$(wslpath -w "$REG_TMP")" 2>&1 | sed 's/^/    /'

echo
echo "Installed. Test it without leaving the terminal:"
echo "    powershell.exe -NoProfile -Command 'Start-Process \"ccode://resume/<session-id>\"'"
echo
echo "Get a session id with:  cr --cmds -d yesterday"
