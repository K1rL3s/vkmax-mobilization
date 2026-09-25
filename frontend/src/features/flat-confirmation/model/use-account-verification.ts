import { authParams, rqClient } from "@/shared/api/instance";
import type { Residency } from "@/shared/model/session";

import type { VerifyInput } from "../domain/verify-method";

export const useAccountVerification = (
  flatId: Residency["flat_id"],
  done: () => Promise<void>,
) => {
  const mutation = rqClient.useMutation("post", "/api/flats/{flat_id}/verify", {
    onSuccess: async (result) => {
      if (result.verified) {
        await done();
      }
    },
  });

  return {
    send: ({ accountNo }: VerifyInput) => {
      if (flatId == null) {
        return;
      }

      mutation.mutate({
        params: { ...authParams(), path: { flat_id: flatId } },
        body: { account_no: accountNo },
      });
    },
    reset: mutation.reset,
    mismatched: mutation.data?.verified === false,
    isPending: mutation.isPending,
    isFailed: mutation.isError,
  };
};
