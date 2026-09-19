import {
  isFinished,
  type RequestListItem,
  type RequestStatus,
} from "@/features/request";

export type FilterId = "all" | "new" | "in_progress" | "on_review" | "done";

type Filter = {
  id: FilterId;
  label: string;
  statuses: RequestStatus[] | null;
};

// «Новые» собирает и принятые: для жителя принятая заявка - всё ещё новая, до
// работ. Серверный фильтр так не умеет, это второй довод считать его у себя
export const FILTERS: Filter[] = [
  { id: "all", label: "Все", statuses: null },
  { id: "new", label: "Новые", statuses: ["new", "accepted"] },
  { id: "in_progress", label: "В работе", statuses: ["in_progress"] },
  { id: "on_review", label: "На приёмке", statuses: ["on_review"] },
  { id: "done", label: "Выполнены", statuses: ["done"] },
];

export type RequestGroup = {
  title: string;
  items: RequestListItem[];
};

export const groupRequests = (
  items: RequestListItem[],
  filterId: FilterId,
): RequestGroup[] => {
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
      title: "Завершённые",
      items: visible.filter((item) => isFinished(item.status)),
    },
  ].filter((group) => group.items.length > 0);
};
