import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";

import { isFinished, isOnReview } from "../domain/status";
import type { RequestCard } from "../domain/types";
import {
  hasStarted,
  pickedWindow,
  visitDay,
  visitLine,
  windowSpan,
  type Visit,
} from "../domain/visit";
import { refetchRequests } from "./use-repeat-request";

const visitHint = (visit: Visit, line: string | null, isUnderWay: boolean) => {
  if (isUnderWay) return "Визит уже начался, поменять время нельзя";
  if (line)
    return "Поменять время можно, пока заявка в работе и визит не начался";

  return `${visitDay(visit.date)} · выберите, когда вы будете дома`;
};

export const useVisitPick = (request: RequestCard, visit: Visit) => {
  const pick = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/visit/{slot_id}",
    { onSettled: refetchRequests },
  );
  const decline = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/visit/{visit_id}/decline",
    { onSettled: refetchRequests },
  );
  const failed = pick.error ?? decline.error;
  const line = visitLine(visit);
  const now = Date.now();
  const picked = pickedWindow(visit);
  const isUnderWay = picked !== undefined && hasStarted(picked, now);
  const canPick =
    !isFinished(request.status) && !isOnReview(request.status) && !isUnderWay;

  return {
    title: line ? `Визит: ${line}` : "УК предлагает время визита",
    hint: visitHint(visit, line, isUnderWay),
    windows: canPick
      ? visit.windows
          .filter((window) => !hasStarted(window, now))
          .map((window) => ({
            id: window.id,
            label: windowSpan(window),
            isPicked: window.id === visit.slot_id,
            isPending:
              pick.isPending &&
              pick.variables.params.path.slot_id === window.id,
          }))
      : [],
    isPicking: pick.isPending || decline.isPending,
    isDeclining: decline.isPending,
    error:
      failed &&
      errorMessage(
        failed,
        "Не получилось сохранить выбор. Проверьте связь и попробуйте ещё раз",
      ),
    decline: () =>
      decline.mutate({
        params: {
          ...authParams(),
          path: { request_id: request.id, visit_id: visit.id },
        },
      }),
    pick: (slotId: number) =>
      pick.mutate({
        params: {
          ...authParams(),
          path: { request_id: request.id, slot_id: slotId },
        },
      }),
  };
};
