import {
  deadlineLeft,
  isFinished,
  isOnReview,
  type RequestStatus,
} from "@/features/request";
import { formatShortDay, formatTime } from "@/shared/lib/format";

import type { AdminRequestItem } from "./request-workflow";

export const FILTERS = [
  { id: "all", label: "Все" },
  { id: "overdue", label: "Просроченные" },
  { id: "question", label: "Ждут ответа жителя" },
  { id: "answered", label: "Есть ответ жителя" },
  { id: "new", label: "Новые" },
  { id: "in_progress", label: "В работе" },
  { id: "on_review", label: "На приёмке" },
  { id: "done", label: "Закрытые" },
] as const;

export type FilterId = (typeof FILTERS)[number]["id"];

const STATUSES: Record<
  Exclude<FilterId, "all" | "overdue" | "question" | "answered">,
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
  if (filter === "question") return !!request.question_asked_at;
  if (filter === "answered") return !!request.resident_answered_at;

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

export const escalationNote = (
  request: AdminRequestItem,
  grouped = false,
): string | null =>
  request.escalated_at && (grouped || overdueNote(request))
    ? `Житель просит руководство с ${formatShortDay(request.escalated_at)} ${formatTime(request.escalated_at)}`
    : null;

export const threadNote = (request: AdminRequestItem) => {
  if (request.resident_answered_at)
    return { text: "Житель ответил", tone: "themed" } as const;
  if (request.question_asked_at)
    return { text: "Ждёт ответа жителя", tone: "neutral" } as const;
  return null;
};

const DANGER_LABEL: Record<NonNullable<AdminRequestItem["danger"]>, string> = {
  gas: "запах газа",
  fire: "дым или огонь",
  electric: "искрит проводка",
  trapped: "застряли в лифте",
  flood_electric: "вода на проводке",
  llm: "похоже на аварию",
};

export const dangerNote = ({ danger }: AdminRequestItem): string | null =>
  danger ? `Опасность: ${DANGER_LABEL[danger]}` : null;
