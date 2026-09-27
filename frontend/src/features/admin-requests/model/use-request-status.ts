import { useState } from "react";

import type { RequestStatus } from "@/features/request";
import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import { statusChoices, type StatusTarget } from "../domain/request-workflow";
import { refreshRequests } from "./refresh-requests";

export const useRequestStatus = (target: StatusTarget) => {
  const choices = statusChoices(target);
  const [picked, setPicked] = useState<RequestStatus | null>(null);
  const status = picked && choices.includes(picked) ? picked : choices[0];
  const requestChange = rqClient.useMutation(
    "post",
    "/api/admin/requests/{request_id}/status",
    { onSuccess: refreshRequests },
  );
  const groupChange = rqClient.useMutation(
    "post",
    "/api/admin/request-groups/{group_id}/status",
    { onSuccess: refreshRequests },
  );
  const change = target.kind === "request" ? requestChange : groupChange;

  return {
    choices,
    status,
    setStatus: setPicked,
    isPending: change.isPending,
    error: change.isError
      ? errorMessage(
          change.error,
          "Не удалось сменить статус. Попробуйте ещё раз.",
        )
      : null,
    submit: () => {
      if (change.isPending) return;
      const body = { status, comment: null };
      if (target.kind === "request")
        requestChange.mutate({
          params: { ...orgParams(), path: { request_id: target.request.id } },
          body,
        });
      else
        groupChange.mutate({
          params: { ...orgParams(), path: { group_id: target.group.id } },
          body,
        });
    },
  };
};
