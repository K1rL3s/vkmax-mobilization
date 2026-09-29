import assert from "node:assert/strict";
import { test } from "node:test";

const { maskDate, isoFromMasked, maskedFromIso } = (await import(
  new URL("../src/shared/lib/date-mask.ts", import.meta.url).href
)) as {
  maskDate: (text: string) => string;
  isoFromMasked: (masked: string) => string;
  maskedFromIso: (iso: string) => string;
};

test("maskDate inserts dots and drops extra characters", () => {
  assert.equal(maskDate("0"), "0");
  assert.equal(maskDate("011"), "01.1");
  assert.equal(maskDate("0110202699"), "01.10.2026");
  assert.equal(maskDate("01.10.2026"), "01.10.2026");
  assert.equal(maskDate("1a/2b"), "12");
});

test("isoFromMasked accepts only a full real date", () => {
  assert.equal(isoFromMasked("01.10.2026"), "2026-10-01");
  assert.equal(isoFromMasked("29.02.2028"), "2028-02-29");
  assert.equal(isoFromMasked("31.02.2026"), "");
  assert.equal(isoFromMasked("01.13.2026"), "");
  assert.equal(isoFromMasked("01.10.20"), "");
});

test("maskedFromIso shows an ISO day and nothing else", () => {
  assert.equal(maskedFromIso("2026-10-01"), "01.10.2026");
  assert.equal(maskedFromIso(""), "");
});
