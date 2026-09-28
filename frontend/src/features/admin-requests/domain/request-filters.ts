import {
  deadlineLeft,
  isFinished,
  isOnReview,
  type RequestStatus,
} from "@/features/request";

import type { AdminRequestItem } from "./request-workflow";

export const FILTERS = [
  { id: "all", label: "Все" },
  { id: "overdue", label: "Просроченные" },
  { id: "new", label: "Новые" },
  { id: "in_progress", label: "В работе" },
  { id: "on_review", label: "На приёмке" },
  { id: "done", label: "Выполнены" },
] as const;

export type FilterId = (typeof FILTERS)[number]["id"];

const STATUSES: Record<
  Exclude<FilterId, "all" | "overdue">,
  RequestStatus[]
> = {
  new: ["new", "accepted"],
  in_progress: ["in_progress"],
  on_review: ["on_review"],
  done: ["done"],
};

export const overdueNote = (request: AdminRequestItem): string | null => {
  if (isFinished(request.status) || isOnReview(request.status)) return null;
  const left = deadlineLeft(request.deadline_at);
  return left?.overdue ? left.text : null;
};

export const matchesFilter = (
  request: AdminRequestItem,
  filter: FilterId,
): boolean => {
  if (filter === "all") return true;
  if (filter === "overdue") return overdueNote(request) !== null;

  return STATUSES[filter].includes(request.status);
};

export const toSections = (items: AdminRequestItem[]) =>
  [
    {
      title: "Активные",
      items: items.filter((item) => !isFinished(item.status)),
    },
    {
      title: "Завершённые",
      items: items.filter((item) => isFinished(item.status)),
    },
  ].filter((section) => section.items.length > 0);
