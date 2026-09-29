import assert from "node:assert/strict";
import { test } from "node:test";

const scheduleUrl = new URL(
  "../src/features/appointments/domain/schedule.ts",
  import.meta.url,
).href;

const { createSchedule } = (await import(scheduleUrl)) as {
  createSchedule: (timeZone: string) => {
    bookedAhead: (appointment: {
      created_at: string;
      starts_at: string;
    }) => boolean;
  };
};

const schedule = createSchedule("Asia/Yekaterinburg");

test("a booking for a later day gets the evening reminder", () => {
  assert.equal(
    schedule.bookedAhead({
      created_at: "2026-09-29T15:00:00Z",
      starts_at: "2026-09-30T05:00:00Z",
    }),
    true,
  );
});

test("a same-day booking in the org time zone gets none", () => {
  assert.equal(
    schedule.bookedAhead({
      created_at: "2026-09-29T20:00:00Z",
      starts_at: "2026-09-30T05:00:00Z",
    }),
    false,
  );
});
