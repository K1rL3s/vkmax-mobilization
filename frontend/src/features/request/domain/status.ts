import type { StatusPillTone } from "@/shared/ui/status-pill";

import type { RequestCompletionReason, RequestStatus } from "./types";

export const STATUS_LABEL: Record<RequestStatus, string> = {
  new: "Новая",
  accepted: "Принята",
  in_progress: "В работе",
  on_review: "На приёмке",
  done: "Выполнена",
};

export const STATUS_TONE: Record<RequestStatus, StatusPillTone> = {
  new: "themed",
  accepted: "themed",
  in_progress: "themed",
  on_review: "promo",
  done: "neutral",
};

export const isFinished = (status: RequestStatus) => status === "done";

export const isOnReview = (status: RequestStatus) => status === "on_review";

export const currentActor = (
  {
    status,
    executor_name: executor,
    author_name: author,
  }: {
    status: RequestStatus;
    executor_name?: string | null;
    author_name?: string | null;
  },
  audience: "resident" | "staff" = "resident",
): string | null => {
  if (status === "done") return null;
  if (status === "new") return "УК принимает заявку";
  if (status === "on_review") {
    if (audience === "resident") return "проверьте работу";
    return author == null ? "УК проверяет работу" : "Житель проверяет работу";
  }
  return executor || audience === "staff" ? null : "УК подбирает исполнителя";
};

export const statusLabel = (
  {
    status,
    completion_reason: reason,
  }: {
    status: RequestStatus;
    completion_reason?: RequestCompletionReason | null;
  },
  audience: "resident" | "staff" = "resident",
): string => {
  if (reason === "resident_rejected") {
    return audience === "resident" ? "Не принята" : "Не принята жителем";
  }
  if (reason !== "resident_canceled") return STATUS_LABEL[status];
  return audience === "resident" ? "Отменена" : "Отменена жителем";
};
