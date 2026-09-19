import { formatDayTime } from "./format";
import type { RequestCard, RequestStatus } from "./types";

// бэковая AUTO_CLOSE_AFTER: в контракт момент автозакрытия не выходит,
// поэтому копия срока живёт здесь - до появления auto_close_at
const AUTO_CLOSE_HOURS = 48;

const ORDER: RequestStatus[] = [
  "new",
  "accepted",
  "in_progress",
  "on_review",
  "done",
];

const STEP_TITLE: Record<RequestStatus, string> = {
  new: "Новая",
  accepted: "Принята УК",
  in_progress: "В работе",
  on_review: "На приёмке",
  done: "Выполнена",
};

export type TimelineStep = {
  status: RequestStatus;
  title: string;
  hint: string | null;
  state: "done" | "current" | "future";
};

// кто закрыл заявку, видно по роли последнего шага: житель принял работу сам
// или сработало автозакрытие
const closedBy = (status: RequestStatus, byRole: string) => {
  if (status !== "done") {
    return "";
  }

  if (byRole === "resident") {
    return " · вы приняли работу";
  }

  return byRole === "system" ? " · закрыта автоматически" : "";
};

const futureHint = (status: RequestStatus, request: RequestCard) => {
  if (status === "on_review" && request.deadline_at) {
    return `Ожидается до ${formatDayTime(request.deadline_at)}`;
  }

  if (status === "done") {
    return `После вашей проверки или через ${AUTO_CLOSE_HOURS} часов`;
  }

  return null;
};

/**
 * Ход заявки: `timeline` отдаёт только случившееся, поэтому будущие шаги
 * достраиваются из текущего статуса - житель должен видеть, что его ждёт.
 */
export const buildTimeline = (request: RequestCard): TimelineStep[] => {
  const happened = new Map(
    request.timeline.map((entry) => [entry.to_status, entry]),
  );
  const current = ORDER.indexOf(request.status);

  return ORDER.map((status, index) => {
    const entry = happened.get(status);
    // «Выполнена» - конец пути, а не текущий шаг: заявке дальше некуда идти
    const state =
      index < current || request.status === "done"
        ? "done"
        : index === current
          ? "current"
          : "future";

    if (index <= current) {
      return {
        status,
        title: STEP_TITLE[status],
        hint: entry
          ? formatDayTime(entry.at) + closedBy(status, entry.by_role)
          : null,
        state,
      };
    }

    return {
      status,
      title: STEP_TITLE[status],
      hint: futureHint(status, request),
      state,
    };
  });
};
