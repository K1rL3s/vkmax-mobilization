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

export type TimelineSource = Pick<
  RequestCard,
  "status" | "timeline" | "deadline_at" | "auto_close_at" | "completion_reason"
> & { author_name?: string | null };

export type TimelineStep = {
  status: RequestStatus;
  title: string;
  hint: string | null;
  state: "done" | "current" | "future";
};

export type TimelineAudience = "resident" | "staff";

const COMPLETION_HINT: Record<
  TimelineAudience,
  Record<RequestCompletionReason, string>
> = {
  resident: {
    resident_accepted: " · вы приняли работу",
    resident_rejected: " · вы не приняли работу",
    auto_closed: " · закрыта автоматически",
  },
  staff: {
    resident_accepted: " · житель принял работу",
    resident_rejected: " · житель не принял работу",
    auto_closed: " · закрыта автоматически",
  },
};

const REVIEW_HINT: Record<TimelineAudience, string> = {
  resident: "После вашей проверки",
  staff: "После проверки жителем",
};

const closedBy = (
  status: RequestStatus,
  request: TimelineSource,
  audience: TimelineAudience,
) => {
  if (status !== "done" || !request.completion_reason) {
    return "";
  }

  return COMPLETION_HINT[audience][request.completion_reason];
};

const futureHint = (
  status: RequestStatus,
  request: TimelineSource,
  audience: TimelineAudience,
) => {
  if (status === "on_review" && request.deadline_at) {
    return `Ожидается до ${formatDayTime(request.deadline_at)}`;
  }

  if (status === "done") {
    if (audience === "staff" && request.author_name == null) {
      return "Закрывает УК: жителя у заявки нет";
    }

    return request.auto_close_at
      ? `${REVIEW_HINT[audience]} или ${formatDayTime(request.auto_close_at)}`
      : REVIEW_HINT[audience];
  }

  return null;
};

/**
 * Ход заявки: `timeline` отдаёт только случившееся, поэтому будущие шаги
 * достраиваются из текущего статуса - житель должен видеть, что его ждёт.
 */
export const buildTimeline = (
  request: TimelineSource,
  audience: TimelineAudience = "resident",
): TimelineStep[] => {
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
          ? formatDayTime(entry.at) + closedBy(status, request, audience)
          : null,
        state,
      };
    }

    return {
      status,
      title: STEP_TITLE[status],
      hint: futureHint(status, request, audience),
      state,
    };
  });
};
