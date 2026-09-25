import { errorDetail, isConflict } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { invalidatePaths, queryClient } from "@/shared/api/query-client";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import type { VerificationRequest } from "./use-verification-list";

const LIST_KEY = ["get", "/api/admin/verification-requests"];

const decisionError = (error: unknown, action: string): string =>
  isConflict(error)
    ? (errorDetail(error) ?? "Запрос уже рассмотрен")
    : `Не получилось ${action}. Проверьте связь и попробуйте ещё раз.`;

export const useVerificationDecision = (
  request: VerificationRequest | null,
  onDone: () => void,
) => {
  const reject = useConfirm<VerificationRequest>();

  const settle = async (updated: VerificationRequest) => {
    queryClient.setQueriesData<
      components["schemas"]["Page_VerificationRequestItem_"]
    >(
      { queryKey: LIST_KEY },
      (page) =>
        page && {
          ...page,
          items: page.items.map((item) =>
            item.id === updated.id ? updated : item,
          ),
        },
    );
    await invalidatePaths("/api/admin/houses/{house_id}", "/api/admin/houses");
    onDone();
  };

  const rereadOnConflict = async (error: unknown) => {
    if (isConflict(error)) {
      await queryClient.invalidateQueries({ queryKey: LIST_KEY });
    }
  };

  const approve = rqClient.useMutation(
    "post",
    "/api/admin/verification-requests/{verification_id}/approve",
    { onSuccess: settle, onError: rereadOnConflict },
  );

  const decline = rqClient.useMutation(
    "post",
    "/api/admin/verification-requests/{verification_id}/reject",
    {
      onSuccess: async (updated) => {
        reject.dismiss();
        await settle(updated);
      },
      onError: rereadOnConflict,
    },
  );

  return {
    isApproving: approve.isPending,
    approveError:
      approve.isError && decisionError(approve.error, "подтвердить"),
    approve: () => {
      if (request === null) {
        return;
      }

      approve.mutate({
        params: { ...orgParams(), path: { verification_id: request.id } },
      });
    },
    rejectTarget: reject.target,
    askReject: () => {
      if (request === null) {
        return;
      }

      decline.reset();
      reject.ask(request);
    },
    dismissReject: () => {
      if (!decline.isPending) {
        reject.dismiss();
      }
    },
    isRejecting: decline.isPending,
    rejectError: decline.isError && decisionError(decline.error, "отклонить"),
    submitReject: (reason: string) => {
      if (request === null) {
        return;
      }

      decline.mutate({
        params: { ...orgParams(), path: { verification_id: request.id } },
        body: { reason },
      });
    },
  };
};
