import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { parse, extract, linkFor, uriFor, isSessionId } from "../cclink.js";

const fixtures = JSON.parse(
  readFileSync(new URL("../fixtures.json", import.meta.url), "utf8"),
);

// These mirror TestFixtures in test_ccl.py against the same file, so a regex
// loosened here and not there (or vice versa) fails on the other side.

test("builds the agreed link and URI for each valid id", () => {
  for (const c of fixtures.valid) {
    assert.equal(linkFor(c.id, fixtures.base), c.link, c.id);
    assert.equal(uriFor(c.id), c.uri, c.id);
  }
});

test("parses link and URI back to the id", () => {
  for (const c of fixtures.valid) {
    assert.equal(parse(c.link, fixtures.base), c.id, c.link);
    assert.equal(parse(c.uri, fixtures.base), c.id, c.uri);
  }
});

test("every accepted variant reaches the same id", () => {
  const expected = fixtures.valid[0].id;
  for (const variant of fixtures.accepted_variants) {
    assert.equal(parse(variant, fixtures.base), expected, variant);
  }
});

test("rejects everything on the rejected list", () => {
  for (const bad of fixtures.rejected) {
    assert.throws(() => parse(bad, fixtures.base), bad || "(empty string)");
  }
});

test("isSessionId is anchored", () => {
  const id = fixtures.valid[0].id;
  assert.ok(isSessionId(id));
  assert.ok(!isSessionId(`x${id}`));
  assert.ok(!isSessionId(`${id}x`));
  assert.ok(!isSessionId(`${id}\nrm -rf ~`));
});

test("extracts an id from free text copied out of a note", () => {
  const expected = fixtures.valid[0].id;
  for (const text of fixtures.extractable) {
    assert.equal(extract(text, fixtures.base), expected, text);
  }
});

test("extract refuses text with no session id in it", () => {
  for (const bad of fixtures.extract_rejected) {
    assert.throws(() => extract(bad, fixtures.base), bad || "(empty string)");
  }
});
