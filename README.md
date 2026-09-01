# cclink

Turn a Claude Code session id into a link you can click from a note.

```
c --resume 01128a7a-ff8a-4ebd-bbca-4c2b16992599
        │  ccl
        ▼
https://cc.buildwithbos.com/#s=01128a7a-ff8a-4ebd-bbca-4c2b16992599
        │  click
        ▼
a Windows Terminal tab, already running claude --resume, in that session's own directory
```

Paste that link into an Obsidian note, a TickTick task, a calendar description,
an email. Clicking it resumes the session.

## Why

A session id written down in a note is a dead end. You have to find it, copy
it, remember which directory that session ran in, and type the command out.
And `obsidian://`-style custom schemes stay inert text in most apps — Obsidian,
TickTick, Gmail and Google Calendar only linkify `http(s)`.

So there are two hops. The `https` link works everywhere and does nothing but
bounce; the `ccode://` URI behind it is what the operating system understands.

## The directory problem

`claude --resume <id>` only finds a session when it runs from the directory
that session was in. The id alone is enough to recover that: the transcript
lives at `~/.claude/projects/<mangled-cwd>/<id>.jsonl` and records its own
`cwd`.

The directory *name* is not used for this. Mangling replaces every `/` with
`-`, which a path that already contains a hyphen makes impossible to reverse —
`-home-bosire-projects-personal-win-scheduled-tasks` has one correct reading
and several plausible wrong ones. The recorded `cwd` has exactly one.

## Your session ids stay private

The id rides in the link's **fragment** (`#s=…`). Browsers never send a
fragment to the server — not in the request line, not in the logs, not in the
`Referer` header. The page is publicly hosted but never learns which session
you opened.

## Nothing but a UUID ever reaches a command line

The payload is a session id, and it is checked at every hop:

| Where | Check |
|---|---|
| `index.html` | Refuses to redirect anything that is not a lowercase UUID — the same defence that stops it being an open redirect wearing this domain. |
| `ccode-open.ps1` | Matches the URI against the id pattern and **rebuilds the command from the capture**. The URI string itself is never forwarded, so a crafted link cannot smuggle a `;` into a Windows Terminal command line. |
| `ccl.py` | Validates again before touching the filesystem or `execv`. A browser is not trusted; neither is the registry. |
| The transcript | Must already exist. |

Worst case for a hostile link is a terminal tab that says "no such session".

## Use it

**Terminal** — `ccl`, a [toolkit](https://github.com/BosTheCoder/toolkit) tool:

```sh
ccl 01128a7a-…                    # → https link
ccl '- `c --resume 01128a7a-…`'   # any line containing an id works
ccl                               # reads the clipboard
ccl -c                            # also copies
ccl -u                            # the ccode:// URI instead
ccl --cwd 01128a7a-…              # where that session ran
cr --cmds -d yesterday | ccl      # straight from the session browser
```

**Browser** — open the page with no fragment and you get a paste box.

## Install the handler (once per Windows machine)

```sh
./windows/install.sh              # writes HKCU only, no administrator
./windows/install.sh --uninstall
```

It registers `ccode://`, copies the PowerShell handler to
`%LOCALAPPDATA%\cclink\`, and records the PATH of the shell you ran it in —
Windows starts the launcher through `wsl.exe --`, which reads no shell config,
so without that recorded PATH `claude` is not findable. Re-run it after moving
`claude` or changing PATH.

The scheme is `ccode`, not `claude`: the Claude desktop app already owns
`claude://`.

Without the handler the link still opens the page, which shows the command to
run by hand. That is also what a phone gets.

## Layout

| File | What it is |
|---|---|
| `index.html` | The page. Redirects when given `#s=…`, otherwise shows the converter. No build step, no dependencies. |
| `cclink.js` | The codec, for the page. |
| `ccl.py` | The codec, the session lookup, and the CLI, for the terminal. Stdlib only. |
| `ccode-resume` | What Windows calls into. Sources the recorded env, then hands off to `ccl.py`. |
| `windows/` | The `ccode://` handler and its installer. |
| `dns.sh` | Points the `CNAME` hostname at Pages on Cloudflare. Idempotent. |
| `fixtures.json` | The contract between the two codecs. |

The codec exists twice because a no-backend design cannot share a runtime.
`fixtures.json` holds the ids, links, URIs and — importantly — the rejects that
**both** test suites assert against, so a pattern loosened on one side fails the
other language's tests rather than quietly producing links that only work in one
direction.

## Tests

```sh
npm test                        # JS codec  (node --test)
python3 -m unittest test_ccl -v # Python codec, session lookup, CLI
```

What they do not cover: that a registry entry fires, or that Windows Terminal
opens a tab. Nothing but clicking a link proves that.

## Hosting

GitHub Pages from `main`, custom domain via `CNAME`, scaffolded and deployed
with [demo-tools](https://github.com/BosTheCoder/demo-tools) (`html` stack,
`pages` target) — `just deploy`, `just status`.

demo-tools automates DNS for its `fly` target but only *prints* the record for
`pages`, so `dns.sh` applies it:

```sh
with-secrets ./dns.sh --check   # what the record is now
with-secrets ./dns.sh           # make it match
```

It forces `proxied=false`. A proxied record breaks GitHub's certificate
issuance, and the symptom is "http works, https does not" up to an hour later.

The repo is public. It holds no secrets and no session ids — those exist only
in fragments, which are never sent anywhere, and in `.ccode-env`, which is not
tracked.
