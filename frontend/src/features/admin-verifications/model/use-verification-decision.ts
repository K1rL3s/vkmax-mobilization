import { errorDetail, isConflict } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import type { VerificationRequest } from "./use-verification-list";

type VerificationPage = components["schemas"]["Page_VerificationRequestItem_"];

const LIST_KEY = ["get", "/api/admin/verification-requests"];

const HOUSE_KEYS = ["/api/admin/houses/{house_id}", "/api/admin/houses"];

const replaceInCache = (updated: VerificationRequest) => {
  queryClient.setQueriesData<VerificationPage>(
    { queryKey: LIST_KEY },
    (page) => {
      if (!page) {
        return page;
      }

      return {
        ...page,
        items: page.items.map((item) =>
          item.id === updated.id ? updated : item,
        ),
      };
    },
  );
};

const refreshHouseCounters = () =>
  Promise.all(
    HOUSE_KEYS.map((path) =>
      queryClient.invalidateQueries({ queryKey: ["get", path] }),
    ),
  );

// 409 приходит и на «уже рассмотрен», и на «переехал»: различает их только
// текст бэка, и повторять не стоит ни то, ни другое
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
    replaceInCache(updated);
    await refreshHouseCounters();
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
      if (approve.isPending || request === null) {
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
      if (decline.isPending || request === null) {
        return;
      }

      decline.mutate({
        params: { ...orgParams(), path: { verification_id: request.id } },
        body: { reason },
      });
    },
  };
};
