import { isConflict } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import type { Residency } from "@/shared/model/session";

import type { VerifyInput } from "../domain/verify-method";

type Done = () => Promise<void>;

export const useOrgRequest = (flatId: Residency["flat_id"], done: Done) => {
  const mutation = rqClient.useMutation(
    "post",
    "/api/flats/{flat_id}/verification-request",
    {
      onSuccess: async () => {
        await done();
      },
      onError: async (error) => {
        // 409 значит, что запрос уже висит. Это не сбой, а состояние, и
        // показать его должен экран подтверждения
        if (!isConflict(error)) {
          return;
        }

        await done();
      },
    },
  );

  return {
    send: ({ accountNo, comment }: VerifyInput) => {
      if (flatId == null) {
        return;
      }

      mutation.mutate({
        params: { ...authParams(), path: { flat_id: flatId } },
        body: {
          account_no: accountNo,
          comment: comment === "" ? null : comment,
        },
      });
    },
    reset: () => mutation.reset(),
    mismatched: false,
    isPending: mutation.isPending,
    isFailed: mutation.isError && !isConflict(mutation.error),
  };
};
