import { generatePath, useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { Routes } from "@/shared/model/routes";

export const refetchRequests = async () => {
  await invalidatePaths("/api/requests/{request_id}");
  await invalidatePaths("/api/requests");
};

export const useRepeatRequest = () => {
  const navigate = useNavigate();
  const idempotency = useIdempotencyKey();

  const repeat = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/repeat",
    {
      onSuccess: async (created) => {
        idempotency.renew();
        await refetchRequests();
        await navigate(
          generatePath(Routes.REQUEST, { requestId: String(created.id) }),
          { replace: true },
        );
      },
    },
  );

  return {
    isPending: repeat.isPending,
    isSuccess: repeat.isSuccess,
    error: repeat.error,
    send: (requestId: number, description: string) =>
      repeat.mutate({
        params: {
          header: {
            ...authParams().header,
            "Idempotency-Key": idempotency.key,
          },
          path: { request_id: requestId },
        },
        body: { description },
      }),
  };
};
