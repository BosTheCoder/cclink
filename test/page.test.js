// The page has no framework and no build step, so nothing catches an element
// id that the script reaches for and the markup no longer has — the page just
// loads and quietly does nothing. These two checks are what a compiler would
// have told us.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import * as codec from "../cclink.js";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const script = html.slice(html.indexOf('<script type="module">'));

test("every id the script looks up exists in the markup", () => {
  const ids = new Set(
    [...script.matchAll(/\$\("([^"]+)"\)/g)].map((m) => m[1]),
  );
  assert.ok(ids.size > 0, "found no $(\"…\") lookups — did the script change shape?");
  for (const id of ids) {
    assert.match(html, new RegExp(`id="${id}"`), `no element with id="${id}"`);
  }
});

test("every data-copy target exists in the markup", () => {
  for (const [, id] of script.matchAll(/data-copy="([^"]+)"/g)) {
    assert.match(html, new RegExp(`id="${id}"`), `data-copy="${id}" has no target`);
  }
  for (const [, id] of html.matchAll(/data-copy="([^"]+)"/g)) {
    assert.match(html, new RegExp(`id="${id}"`), `data-copy="${id}" has no target`);
  }
});

test("every name the page imports is exported by the codec", () => {
  const imported = /import \{([^}]+)\} from "\.\/cclink\.js"/.exec(script);
  assert.ok(imported, "the page no longer imports from ./cclink.js");
  for (const name of imported[1].split(",").map((s) => s.trim()).filter(Boolean)) {
    assert.ok(name in codec, `index.html imports ${name}, which cclink.js does not export`);
  }
});
