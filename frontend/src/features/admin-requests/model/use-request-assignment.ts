import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import type { AdminRequest } from "../domain/request-workflow";
import { refreshRequests } from "./refresh-requests";

export const useRequestAssignment = (request: AdminRequest) => {
  const executors = rqClient.useQuery("get", "/api/admin/executors", {
    params: orgParams(),
  });
  const assign = rqClient.useMutation(
    "post",
    "/api/admin/requests/{request_id}/assign",
    { onSuccess: refreshRequests },
  );

  const sorted = [...(executors.data ?? [])].sort((first, second) => {
    if (first.user_id === request.executor_user_id) return -1;
    if (second.user_id === request.executor_user_id) return 1;
    return first.active_requests - second.active_requests;
  });

  return {
    executors: sorted,
    selectedId: request.executor_user_id,
    isLoading: executors.isPending,
    isLoadError: executors.isError,
    loadError: executors.error,
    isPending: assign.isPending,
    pendingId: assign.isPending ? assign.variables?.body.user_id : undefined,
    error: assign.isError
      ? errorMessage(
          assign.error,
          "Не удалось назначить исполнителя. Попробуйте ещё раз.",
        )
      : null,
    retry: () => void executors.refetch(),
    assign: (userId: number) => {
      if (assign.isPending || userId === request.executor_user_id) return;
      assign.mutate({
        params: { ...orgParams(), path: { request_id: request.id } },
        body: { user_id: userId },
      });
    },
  };
};
