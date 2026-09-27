import { isConflict } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { houseParams } from "@/shared/model/session";

export const useAccessRequests = () => {
  const list = rqClient.useQuery("get", "/api/access-requests", {
    params: houseParams(),
  });

  const pick = rqClient.useMutation(
    "post",
    "/api/access-requests/{access_request_id}/slots/{slot_id}",
    {
      onSettled: () => invalidatePaths("/api/access-requests"),
    },
  );

  const failedFor = (accessRequestId: number) =>
    pick.isError &&
    pick.variables.params.path.access_request_id === accessRequestId;

  return {
    items: list.data ?? [],
    isPending: list.isPending,
    isError: list.isError,
    loadError: list.error,
    retry: () => void list.refetch(),
    isPicking: pick.isPending,
    pendingSlotId: pick.isPending
      ? pick.variables.params.path.slot_id
      : undefined,
    needsConfirmation: (accessRequestId: number) =>
      failedFor(accessRequestId) && pick.error?.status === 404,
    errorOf: (accessRequestId: number) => {
      if (!failedFor(accessRequestId) || pick.error?.status === 404) {
        return null;
      }

      return isConflict(pick.error)
        ? "В этом окне места закончились, выберите другое"
        : "Не получилось сохранить выбор. Проверьте связь и попробуйте ещё раз";
    },
    pick: (accessRequestId: number, slotId: number) => {
      if (!pick.isPending) {
        pick.mutate({
          params: {
            ...authParams(),
            path: { access_request_id: accessRequestId, slot_id: slotId },
          },
        });
      }
    },
  };
};
