import type { CancelReason } from "./types";

export const CANCEL_REASONS: Record<CancelReason, string> = {
  mistake: "Подана по ошибке",
  resolved: "Проблема решилась сама",
  fixed_myself: "Починили сами или вызвали мастера",
  duplicate: "Уже есть другая заявка",
  other: "Другое",
};

export const cancelFormConstraints = { comment: 500 };
