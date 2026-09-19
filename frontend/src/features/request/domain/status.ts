import type { IconTileTone } from "@/shared/ui/icon-tile";

import type { RequestStatus } from "./types";

export const STATUS_LABEL: Record<RequestStatus, string> = {
  new: "Новая",
  accepted: "Принята",
  in_progress: "В работе",
  on_review: "На приёмке",
  done: "Выполнена",
};

// приёмка выделена цветом: это единственный статус, на котором заявка ждёт
// действия жителя, а не УК
export const STATUS_TONE: Record<RequestStatus, IconTileTone> = {
  new: "themed",
  accepted: "themed",
  in_progress: "themed",
  on_review: "promo",
  done: "neutral",
};

export const isFinished = (status: RequestStatus) => status === "done";

// приёмка - единственный статус, на котором ход за жителем: её проверяют и
// Главная, и лента, и карточка
export const isOnReview = (status: RequestStatus) => status === "on_review";
