import assert from "node:assert/strict";
import { test } from "node:test";

const { duration } = (await import(
  new URL("../src/shared/lib/format.ts", import.meta.url).href
)) as { duration: (ms: number) => string };

const HOUR = 60 * 60 * 1000;

test("days round to the nearest one, so a fresh 3-day deadline reads as 3 days", () => {
  assert.equal(duration(72 * HOUR - 60_000), "3 дня");
  assert.equal(duration(36 * HOUR - 60_000), "1 день");
  assert.equal(duration(24 * HOUR), "1 день");
  assert.equal(duration(5 * HOUR + 30 * 60_000), "5 ч 30 мин");
});
