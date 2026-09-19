import { formatDayTime } from "@/shared/lib/format";
import { isFinished } from "./status";
import type {
  RequestCard,
  RequestCompletionReason,
  RequestStatus,
} from "./types";

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

/**
 * Автозакрытие приёмки: момент считает бэк и присылает `auto_close_at`, у
 * заявки вне приёмки поля нет. Полоса заполняется от шага «На приёмке».
 */
export const autoClose = (request: RequestCard, now = Date.now()) => {
  const sent = request.timeline.find(
    (entry) => entry.to_status === "on_review",
  );

  if (!sent || !request.auto_close_at) {
    return null;
  }

  const from = new Date(sent.at).getTime();
  const at = new Date(request.auto_close_at).getTime();

  return {
    sentAt: sent.at,
    at: request.auto_close_at,
    left: at - now,
    progress: Math.min(1, Math.max(0, (now - from) / (at - from))),
  };
};

// «Выполнена» - конец пути, а не текущий шаг: заявке дальше некуда идти
const stepState = (
  index: number,
  current: number,
  finished: boolean,
): TimelineStep["state"] => {
  if (index < current || finished) {
    return "done";
  }

  return index === current ? "current" : "future";
};

export type TimelineStep = {
  status: RequestStatus;
  title: string;
  hint: string | null;
  state: "done" | "current" | "future";
};

const COMPLETION_HINT: Record<RequestCompletionReason, string> = {
  resident_accepted: " · вы приняли работу",
  resident_rejected: " · вы не приняли работу",
  auto_closed: " · закрыта автоматически",
};

const closedBy = (status: RequestStatus, request: RequestCard) => {
  if (status !== "done" || !request.completion_reason) {
    return "";
  }

  return COMPLETION_HINT[request.completion_reason];
};

const futureHint = (status: RequestStatus, request: RequestCard) => {
  if (status === "on_review" && request.deadline_at) {
    return `Ожидается до ${formatDayTime(request.deadline_at)}`;
  }

  if (status === "done") {
    return request.auto_close_at
      ? `После вашей проверки или ${formatDayTime(request.auto_close_at)}`
      : "После вашей проверки";
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
    const state = stepState(index, current, isFinished(request.status));

    if (index <= current) {
      return {
        status,
        title: STEP_TITLE[status],
        hint: entry
          ? formatDayTime(entry.at) + closedBy(status, request)
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
