import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import type { RequestCard } from "../domain/types";

import { refetchRequests } from "../model/use-repeat-request";
import { useRejection } from "./use-rejection";

export const useReview = (request: RequestCard) => {
  const rejection = useRejection(request, "«Сделано плохо»");
  const params = { ...authParams(), path: { request_id: request.id } };

  const accept = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/accept",
    { onSuccess: refetchRequests },
  );
  const autoClose = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/demo/auto-close",
    { onSuccess: refetchRequests },
  );

  const isAccepting = accept.isPending || accept.isSuccess;

  return {
    rejection,
    isAccepting,
    error:
      (accept.error &&
        errorMessage(
          accept.error,
          "Ответ не ушёл. Проверьте связь и попробуйте ещё раз",
        )) ??
      rejection.error,
    canAccept: !isAccepting && !rejection.isSending,
    canReject: rejection.canSend && !isAccepting,
    accept: () => accept.mutate({ params }),
    canDemoAutoClose: request.can_demo_auto_close,
    isAutoClosing: autoClose.isPending,
    autoCloseError:
      autoClose.error &&
      errorMessage(
        autoClose.error,
        "Заявка не закрылась. Проверьте связь и попробуйте ещё раз",
      ),
    demoAutoClose: () => autoClose.mutate({ params }),
  };
};
