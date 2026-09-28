import assert from "node:assert/strict";
import { test } from "node:test";

const hapticUrl = new URL("../src/shared/lib/max/haptic.ts", import.meta.url)
  .href;

const { haptic } = (await import(hapticUrl)) as {
  haptic: Record<"success" | "error" | "select", () => void>;
};

const settle = () => new Promise((resolve) => setTimeout(resolve));

const mount = (feedback: unknown) => {
  Object.assign(globalThis, {
    window: { WebApp: { HapticFeedback: feedback } },
  });
};

test("maps each helper to its bridge call", async () => {
  const calls: string[] = [];
  mount({
    notificationOccurred: async (type: string) => calls.push(type),
    selectionChanged: async () => calls.push("selection"),
  });

  haptic.success();
  haptic.error();
  haptic.select();
  await settle();

  assert.deepEqual(calls, ["success", "error", "selection"]);
});

test("does nothing without the bridge or its haptics", () => {
  Object.assign(globalThis, { window: {} });
  haptic.success();

  mount(undefined);
  haptic.select();
});

test("swallows a rejected or throwing call", async () => {
  const rejections: unknown[] = [];
  const track = (reason: unknown) => rejections.push(reason);
  process.on("unhandledRejection", track);

  mount({
    notificationOccurred: () => Promise.reject(new Error("web client")),
    selectionChanged: () => {
      throw new Error("old client");
    },
  });

  haptic.error();
  haptic.select();
  await settle();

  process.off("unhandledRejection", track);
  assert.deepEqual(rejections, []);
});
