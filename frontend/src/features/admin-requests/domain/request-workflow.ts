import {
  CATEGORY_ICON,
  type RequestCategory,
  type RequestStatus,
} from "@/features/request";
import type { components } from "@/shared/api/schema/generated";

export type AdminRequest = components["schemas"]["AdminRequestCard"];
export type AdminRequestItem = components["schemas"]["AdminRequestListItem"];
export type RequestGroup = components["schemas"]["RequestGroupCard"];

export type StatusTarget =
  | { kind: "request"; request: AdminRequest }
  | { kind: "group"; group: RequestGroup };

export const CHANNEL_LABEL: Record<AdminRequestItem["channel"], string> = {
  miniapp: "Мини-апп",
  bot: "Бот",
  chat: "Чат дома",
  phone: "Звонок",
};

export const STATUS_ACTION: Record<RequestStatus, string> = {
  new: "Вернуть в новые",
  accepted: "Принять заявку",
  in_progress: "Начать работы",
  on_review: "Отправить на приёмку",
  done: "Закрыть заявку",
};

const statusOrder: RequestStatus[] = [
  "new",
  "accepted",
  "in_progress",
  "on_review",
  "done",
];

export const statusChoices = (target: StatusTarget): RequestStatus[] => {
  if (target.kind === "request") {
    const request = target.request;
    const next = statusOrder[statusOrder.indexOf(request.status) + 1];
    const requiresResidentReview =
      next === "done" && request.author_name != null;
    return !next || requiresResidentReview ? [] : [next];
  }

  const { requests, status } = target.group;
  if (status === "closed" || requests.length === 0) return [];

  return statusOrder.filter((next, index) => {
    const wouldMoveBackwards = requests.some(
      (request) => statusOrder.indexOf(request.status) > index,
    );
    const hasChanges = requests.some((request) => request.status !== next);
    const requiresResidentReview =
      next === "done" &&
      requests.some(
        (request) => request.status !== "done" && request.author_name != null,
      );
    return !wouldMoveBackwards && hasChanges && !requiresResidentReview;
  });
};

export const isCategory = (value: unknown): value is RequestCategory =>
  typeof value === "string" && Object.hasOwn(CATEGORY_ICON, value);
