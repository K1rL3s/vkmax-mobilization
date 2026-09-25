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

export const autoClose = (request: RequestCard) => {
  const sent = request.timeline.find(
    (entry) => entry.to_status === "on_review",
  );

  if (!sent || !request.auto_close_at) {
    return null;
  }

  const from = new Date(sent.at).getTime();
  const at = new Date(request.auto_close_at).getTime();
  const now = Date.now();

  return {
    sentAt: sent.at,
    at: request.auto_close_at,
    left: at - now,
    progress: Math.min(1, Math.max(0, (now - from) / (at - from))),
  };
};

type TimelineSource = Pick<
  RequestCard,
  "status" | "timeline" | "deadline_at" | "auto_close_at" | "completion_reason"
> & { author_name?: string | null };

export type TimelineStep = {
  status: RequestStatus;
  title: string;
  hint: string | null;
  state: "done" | "current" | "future";
};

type TimelineAudience = "resident" | "staff";

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

export const buildTimeline = (
  request: TimelineSource,
  audience: TimelineAudience = "resident",
): TimelineStep[] => {
  const happened = new Map(
    request.timeline.map((entry) => [entry.to_status, entry.at]),
  );
  const current = ORDER.indexOf(request.status);
  const finished = isFinished(request.status);

  return ORDER.map((status, index) => {
    const at = happened.get(status);
    const closedBy =
      status === "done" && request.completion_reason
        ? COMPLETION_HINT[audience][request.completion_reason]
        : "";

    return {
      status,
      title: STEP_TITLE[status],
      hint:
        index > current
          ? futureHint(status, request, audience)
          : at
            ? formatDayTime(at) + closedBy
            : null,
      state:
        index < current || finished
          ? "done"
          : index === current
            ? "current"
            : "future",
    };
  });
};
