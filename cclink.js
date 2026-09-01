// cclink codec — Claude Code session id <-> ccode:// URI <-> https bounce URL.
//
// The id rides in the bounce URL's *fragment*. Browsers never send a fragment
// to the server, so this page is publicly hosted but never learns which session
// you opened. A UUID needs no encoding: its alphabet (0-9 a-f -) contains
// nothing a linkifier will truncate on.
//
// Mirrored in ccl.py. fixtures.json is the contract between the two.

export const DEFAULT_BASE = "https://cc.buildwithbos.com";

const SCHEME = "ccode";

// Anchored, lowercase hex and hyphen only. This is the security boundary: the
// page hands this value to the OS, so nothing that is not a UUID may pass.
const SESSION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function isSessionId(value) {
  return SESSION_ID.test(value);
}

// Extract a session id from an id, a ccode:// URI, or a cclink https URL.
// Throws on anything else — including an https link on another origin, which
// is what stops this from being an open redirect wearing our domain.
export function parse(value, base = DEFAULT_BASE) {
  const raw = String(value ?? "").trim().replace(/^["']|["']$/g, "");
  const root = base.replace(/\/+$/, "");
  let candidate;

  if (raw.toLowerCase().startsWith(`${SCHEME}://`)) {
    const rest = raw.slice(SCHEME.length + 3);
    if (!rest.startsWith("resume/")) {
      throw new Error(`unsupported ${SCHEME}:// action (expected ${SCHEME}://resume/<id>)`);
    }
    candidate = rest.slice("resume/".length).replace(/\/+$/, "");
  } else if (raw.includes("://")) {
    if (!raw.startsWith(`${root}/`) && raw.replace(/\/+$/, "") !== root) {
      throw new Error(`link is not on ${root}`);
    }
    const hash = raw.slice(raw.indexOf("#") + 1);
    if (raw.indexOf("#") === -1 || !hash.startsWith("s=")) {
      throw new Error("link has no #s=<id> fragment");
    }
    candidate = hash.slice(2);
  } else {
    candidate = raw;
  }

  candidate = candidate.toLowerCase();
  if (!isSessionId(candidate)) throw new Error("not a Claude Code session id");
  return candidate;
}

// Lenient front door: pull the first UUID-shaped run out of free text, so a
// line copied straight from a note ("- `c --resume <id>`") works. The result
// still goes through parse(), so leniency here buys no leniency downstream.
export function extract(text, base = DEFAULT_BASE) {
  const raw = String(text ?? "").trim();
  try {
    return parse(raw, base);
  } catch (err) {
    // Boundaries matter: without them a 37-hex run would yield its first 36
    // characters, quietly linking to a different session than the one pasted.
    const m = /(?<![0-9a-fA-F-])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F-])/.exec(raw);
    if (!m) throw err;
    return parse(m[0], base);
  }
}

export function linkFor(sessionId, base = DEFAULT_BASE) {
  return `${base.replace(/\/+$/, "")}/#s=${parse(sessionId, base)}`;
}

export function uriFor(sessionId) {
  return `${SCHEME}://resume/${parse(sessionId)}`;
}

// The command to run by hand where the handler is not installed — a phone, or
// a machine that has never had ccode.reg imported.
export function commandFor(sessionId) {
  return `c --resume ${parse(sessionId)}`;
}
