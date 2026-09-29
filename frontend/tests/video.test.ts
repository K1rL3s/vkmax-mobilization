import assert from "node:assert/strict";
import { test, type TestContext } from "node:test";

const { checkVideo } = await import(
  new URL("../src/shared/ui/attachment-picker/check-video.ts", import.meta.url)
    .href
);

const file = (type = "video/mp4", size = 1) =>
  new File([new Uint8Array(size)], "clip.mp4", { type });

const metadata = (t: TestContext, duration: number, fails = false) => {
  const video = {
    duration,
    onloadedmetadata: null as null | (() => void),
    onerror: null as null | (() => void),
    removeAttribute() {},
    load() {},
    set src(_value: string) {
      queueMicrotask(() =>
        fails ? this.onerror?.() : this.onloadedmetadata?.(),
      );
    },
  };
  t.mock.method(globalThis, "setTimeout", () => 1);
  t.mock.method(URL, "createObjectURL", () => "blob:test");
  const revoke = t.mock.method(URL, "revokeObjectURL", () => {});
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { createElement: () => video },
  });
  t.after(() => {
    Reflect.deleteProperty(globalThis, "document");
  });
  return revoke;
};

test("images skip video metadata", async () => {
  await checkVideo(file("image/jpeg"), 2);
});

for (const [name, input, count, message] of [
  ["size", file("video/mp4", 51 * 1024 * 1024), 0, /Видео больше 50 МБ/],
  ["count", file(), 2, /не больше 2 видео/],
  ["type", file("video/x-msvideo"), 0, /MP4 или MOV/],
] as const) {
  test(`rejects video ${name} before reading metadata`, async () => {
    await assert.rejects(checkVideo(input, count), message);
  });
}

for (const duration of [0, Infinity, NaN, 61]) {
  test(`rejects duration ${duration} and releases preview`, async (t) => {
    const revoke = metadata(t, duration);
    await assert.rejects(
      checkVideo(file(), 0),
      duration === 61 ? /длиннее 60 секунд/ : /определить длительность/,
    );
    assert.equal(revoke.mock.callCount(), 1);
  });
}

test("accepts a 60 second MOV and releases metadata preview", async (t) => {
  const revoke = metadata(t, 60);
  await checkVideo(file("video/quicktime"), 1);
  assert.equal(revoke.mock.callCount(), 1);
});

test("unreadable video gives a useful error", async (t) => {
  metadata(t, 0, true);
  await assert.rejects(checkVideo(file(), 0), /Не удалось прочитать видео/);
});
