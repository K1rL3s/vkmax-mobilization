import assert from "node:assert/strict";
import { test } from "node:test";

const { canGoBack } = (await import(
  new URL("../src/shared/lib/max/can-go-back.ts", import.meta.url).href
)) as { canGoBack: (handlerCount: number, historyState: unknown) => boolean };

test("shows back on a pushed screen with in-app history", () => {
  assert.equal(canGoBack(1, { usr: null, key: "a1", idx: 2 }), true);
});

test("leaves the close cross on the first entry, even after a replace", () => {
  assert.equal(canGoBack(1, { usr: null, key: "default", idx: 0 }), false);
  assert.equal(canGoBack(1, { usr: null, key: "x7", idx: 0 }), false);
});

test("leaves the close cross without a pushed screen or router state", () => {
  assert.equal(canGoBack(0, { idx: 3 }), false);
  assert.equal(canGoBack(1, null), false);
  assert.equal(canGoBack(1, { idx: "1" }), false);
});
