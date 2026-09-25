import { useQuery } from "@tanstack/react-query";

import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useSession } from "@/shared/model/session";

export const useCharges = () => {
  const { currentResidency: residency } = useSession();
  const flatId = residency?.flat_id ?? null;
  const access = (() => {
    if (!residency?.is_connected) {
      return "none";
    }

    if (!residency.can_see_charges) {
      return "tenant";
    }

    if (flatId === null) {
      return "none";
    }

    return residency.verified ? "open" : "unverified";
  })();

  const list = useQuery({
    ...rqClient.queryOptions("get", "/api/flats/{flat_id}/charges", {
      params: {
        ...authParams(),
        path: { flat_id: flatId ?? 0 },
        query: { limit: 24 },
      },
    }),
    enabled: access === "open",
  });

  return { residency, access, list };
};

export const useCharge = (chargeId: number) => {
  const options = {
    params: { ...authParams(), path: { charge_id: chargeId } },
  };

  const enabled = chargeId > 0;

  const card = rqClient.useQuery("get", "/api/charges/{charge_id}", options, {
    enabled,
  });

  const breakdown = rqClient.useQuery(
    "get",
    "/api/charges/{charge_id}/breakdown",
    options,
    { enabled },
  );

  const pay = rqClient.useMutation("post", "/api/charges/{charge_id}/pay", {
    onSettled: () =>
      invalidatePaths(
        "/api/charges/{charge_id}",
        "/api/flats/{flat_id}/charges",
      ),
  });

  return {
    card,
    breakdown,
    pay,
    submitPay: () => pay.mutate(options),
  };
};
