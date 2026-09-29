import assert from "node:assert/strict";
import { test } from "node:test";

const scanCodeUrl = new URL(
  "../src/shared/lib/max/scan-code.ts",
  import.meta.url,
).href;

const { canScanCode, scanCode } = (await import(scanCodeUrl)) as {
  canScanCode: () => boolean;
  scanCode: () => Promise<string | null>;
};

const QR = "ST00012|Name=Демо-УК|persAcc=0000000012";

const mount = (openCodeReader: unknown, platform: string | null = "ios") => {
  Object.assign(globalThis, {
    window: { WebApp: { openCodeReader, platform } },
  });
};

test("returns the scanned value and lets the gallery in", async () => {
  const calls: unknown[] = [];
  mount(async (fileSelect: unknown) => {
    calls.push(fileSelect);
    return { value: QR };
  });

  assert.equal(canScanCode(), true);
  assert.equal(await scanCode(), QR);
  assert.deepEqual(calls, [true]);
});

test("takes a bare string from the bridge too", async () => {
  mount(async () => QR);

  assert.equal(await scanCode(), QR);
});

test("gives null without the bridge or its reader", async () => {
  Object.assign(globalThis, { window: {} });
  assert.equal(canScanCode(), false);
  assert.equal(await scanCode(), null);

  mount(undefined);
  assert.equal(canScanCode(), false);
  assert.equal(await scanCode(), null);
});

test("gives null on a cancel, a throw or an empty answer", async () => {
  mount(() => Promise.reject(new Error("cancelled")));
  assert.equal(await scanCode(), null);

  mount(() => {
    throw new Error("old client");
  });
  assert.equal(await scanCode(), null);

  mount(async () => ({ value: "" }));
  assert.equal(await scanCode(), null);

  mount(async () => ({}));
  assert.equal(await scanCode(), null);
});

test("hides the scanner off the phone although the bridge has the reader", () => {
  for (const platform of ["desktop", "web", null]) {
    mount(async () => ({ value: QR }), platform);
    assert.equal(canScanCode(), false);
  }

  mount(async () => ({ value: QR }), "android");
  assert.equal(canScanCode(), true);
});
