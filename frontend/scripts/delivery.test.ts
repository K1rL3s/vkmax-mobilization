import assert from "node:assert/strict";
import { test } from "node:test";

type Message = { delivery: string | null; read: boolean; created_at: string };

const { deliveryMark } = (await import(
  new URL("../src/features/request/domain/delivery.ts", import.meta.url).href
)) as { deliveryMark: (message: Message) => string | null };

const ago = (minutes: number) =>
  new Date(Date.now() - minutes * 60 * 1000).toISOString();

test("a pending notice reads as sending for 10 minutes, then as no data", () => {
  const pending = { delivery: "pending", read: false };

  assert.equal(deliveryMark({ ...pending, created_at: ago(9) }), "pending");
  assert.equal(deliveryMark({ ...pending, created_at: ago(11) }), "unknown");
  assert.equal(
    deliveryMark({ ...pending, read: true, created_at: ago(11) }),
    "read",
  );
});

test("a message without delivery has no mark, a settled one keeps its own", () => {
  assert.equal(
    deliveryMark({ delivery: null, read: false, created_at: ago(1) }),
    null,
  );
  assert.equal(
    deliveryMark({ delivery: "bot_stopped", read: false, created_at: ago(60) }),
    "bot_stopped",
  );
});
