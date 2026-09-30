import assert from "node:assert/strict";
import { test } from "node:test";

const { statusLabel } = (await import(
  new URL("../src/features/request/domain/status.ts", import.meta.url).href
)) as {
  statusLabel: (
    request: { status: string; completion_reason?: string | null },
    audience?: "resident" | "staff",
  ) => string;
};

test("a canceled request reads as canceled, other closed ones as done", () => {
  const canceled = { status: "done", completion_reason: "resident_canceled" };

  assert.equal(statusLabel(canceled), "Отменена");
  assert.equal(statusLabel(canceled, "staff"), "Отменена жителем");
  assert.equal(
    statusLabel({ status: "done", completion_reason: "auto_closed" }, "staff"),
    "Выполнена",
  );
  assert.equal(statusLabel({ status: "in_progress" }), "В работе");
});

test("a request the resident rejected reads as not accepted", () => {
  const rejected = { status: "done", completion_reason: "resident_rejected" };

  assert.equal(statusLabel(rejected), "Не принята");
  assert.equal(statusLabel(rejected, "staff"), "Не принята жителем");
});
