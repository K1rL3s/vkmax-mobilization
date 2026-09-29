import assert from "node:assert/strict";
import { test } from "node:test";

const { weekRange } = (await import(
  new URL("../src/features/admin-analytics/domain/week.ts", import.meta.url)
    .href
)) as { weekRange: (monday: string) => string };

test("shows a Monday-to-Sunday week with its inclusive last day", () => {
  assert.equal(weekRange("2026-08-17"), "17.08-23.08");
  assert.equal(weekRange("2026-08-31"), "31.08-06.09");
});

test("adds the years only when the week crosses New Year", () => {
  assert.equal(weekRange("2025-12-29"), "29.12.2025-04.01.2026");
});
