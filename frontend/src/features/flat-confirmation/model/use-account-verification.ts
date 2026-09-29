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

  const verify = (body: { account_no: string } | { payment_qr: string }) => {
    if (flatId == null) {
      return;
    }

    mutation.mutate({
      params: { ...authParams(), path: { flat_id: flatId } },
      body,
    });
  };

  return {
    send: ({ accountNo }: VerifyInput) => verify({ account_no: accountNo }),
    sendQr: (paymentQr: string) => verify({ payment_qr: paymentQr }),
    retry: () => mutation.variables && mutation.mutate(mutation.variables),
    reset: mutation.reset,
    mismatched: mutation.data?.verified === false,
    isPending: mutation.isPending,
    isFailed: mutation.isError,
    failure: mutation.error,
  };
};
