import { isConflict } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import type { Residency } from "@/shared/model/session";

import type { VerifyInput } from "../domain/verify-method";

export const useOrgRequest = (
  flatId: Residency["flat_id"],
  done: () => Promise<void>,
) => {
  const mutation = rqClient.useMutation(
    "post",
    "/api/flats/{flat_id}/verification-request",
    {
      onSuccess: () => done(),
      onError: async (error) => {
        if (isConflict(error)) {
          await done();
        }
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
    reset: mutation.reset,
    mismatched: false,
    isPending: mutation.isPending,
    isFailed: mutation.isError && !isConflict(mutation.error),
  };
};
