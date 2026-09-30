import {
  isFinished,
  type RequestListItem,
  type RequestStatus,
} from "@/features/request";

export type FilterId = "all" | "new" | "in_progress" | "on_review" | "done";

export const FILTERS: {
  id: FilterId;
  label: string;
  statuses: RequestStatus[] | null;
}[] = [
  { id: "all", label: "Все", statuses: null },
  { id: "new", label: "Новые", statuses: ["new", "accepted"] },
  { id: "in_progress", label: "В работе", statuses: ["in_progress"] },
  { id: "on_review", label: "На приёмке", statuses: ["on_review"] },
  { id: "done", label: "Закрытые", statuses: ["done"] },
];

export const groupRequests = (items: RequestListItem[], filterId: FilterId) => {
  const statuses = FILTERS.find(({ id }) => id === filterId)?.statuses;
  const visible = statuses
    ? items.filter((item) => statuses.includes(item.status))
    : items;

  return [
    {
      title: "Активные",
      items: visible.filter((item) => !isFinished(item.status)),
    },
    {
      title: "Закрытые",
      items: visible.filter((item) => isFinished(item.status)),
    },
  ].filter((group) => group.items.length > 0);
};
