import assert from "node:assert/strict";
import { test } from "node:test";

const filtersUrl = new URL(
  "../src/features/admin-houses/domain/map-filters.ts",
  import.meta.url,
).href;

type SignedHouse = {
  open: number;
  overdue: number;
  escalated: number;
  urgent_id?: number | null;
  poll_id?: number | null;
  appointments_today: number;
};

const { metersTone, residentsTone, parseRange, houseSignature } = (await import(
  filtersUrl
)) as {
  metersTone: (percent: number | null | undefined) => string;
  residentsTone: (
    residents: number | null | undefined,
    flats: number | null | undefined,
  ) => string;
  parseRange: (
    value: string | null | undefined,
    scale: number,
  ) => [number | undefined, number | undefined];
  houseSignature: (house: SignedHouse) => string;
};

test("meters tone switches at 50% and 80%", () => {
  assert.equal(metersTone(null), "muted");
  assert.equal(metersTone(4999), "red");
  assert.equal(metersTone(5000), "yellow");
  assert.equal(metersTone(7999), "yellow");
  assert.equal(metersTone(8000), "green");
});

test("residents tone switches at 10% and 30% of flats", () => {
  assert.equal(residentsTone(null, 100), "muted");
  assert.equal(residentsTone(5, 0), "muted");
  assert.equal(residentsTone(9, 100), "red");
  assert.equal(residentsTone(10, 100), "yellow");
  assert.equal(residentsTone(29, 100), "yellow");
  assert.equal(residentsTone(30, 100), "green");
});

test("ranges scale to the API units and keep open sides open", () => {
  assert.deepEqual(parseRange("80-100", 100), [8000, 10000]);
  assert.deepEqual(parseRange("35-50", 10), [350, 500]);
  assert.deepEqual(parseRange("-50", 10), [undefined, 500]);
  assert.deepEqual(parseRange("abc", 10), [undefined, undefined]);
});

test("house signature changes with each of its fields", () => {
  const house: SignedHouse = {
    open: 1,
    overdue: 1,
    escalated: 1,
    urgent_id: 1,
    poll_id: 1,
    appointments_today: 1,
  };
  const base = houseSignature(house);

  for (const key of Object.keys(house) as (keyof SignedHouse)[]) {
    assert.notEqual(houseSignature({ ...house, [key]: 2 }), base, key);
  }
});
