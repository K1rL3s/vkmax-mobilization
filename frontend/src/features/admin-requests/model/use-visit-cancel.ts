import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import { refreshRequests } from "./refresh-requests";

export const useVisitCancel = (requestId: number) => {
  const confirm = useConfirm();
  const cancel = rqClient.useMutation(
    "delete",
    "/api/admin/requests/{request_id}/visit",
    {
      onSuccess: async () => {
        confirm.dismiss();
        await refreshRequests();
      },
    },
  );

  return {
    isOpen: confirm.isOpen,
    isPending: cancel.isPending,
    error:
      cancel.error &&
      errorMessage(
        cancel.error,
        "Визит не отменился. Проверьте связь и попробуйте ещё раз",
      ),
    ask: () => {
      cancel.reset();
      confirm.ask();
    },
    dismiss: () => {
      if (!cancel.isPending) {
        confirm.dismiss();
      }
    },
    confirm: () =>
      cancel.mutate({
        params: { ...orgParams(), path: { request_id: requestId } },
      }),
  };
};
