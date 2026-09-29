import assert from "node:assert/strict";
import { test } from "node:test";

const { slotLabels } = (await import(
  new URL("../src/features/admin-reception/domain/day.ts", import.meta.url)
    .href
)) as {
  slotLabels: (spans: [string, string][], minutes: number) => string[];
};

test("skips the lunch break like the backend windows do", () => {
  assert.deepEqual(
    slotLabels(
      [
        ["09:00", "10:00"],
        ["11:00", "12:00"],
      ],
      30,
    ),
    ["09:00-09:30", "09:30-10:00", "11:00-11:30", "11:30-12:00"],
  );
});

test("drops a trailing slot that does not fit before the window ends", () => {
  assert.deepEqual(slotLabels([["09:00", "10:10"]], 30), [
    "09:00-09:30",
    "09:30-10:00",
  ]);
  assert.deepEqual(slotLabels([["09:00", "09:20"]], 30), []);
});

test("gives nothing for a zero slot length", () => {
  assert.deepEqual(slotLabels([["09:00", "18:00"]], 0), []);
});
