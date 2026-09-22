import { useQuery } from "@tanstack/react-query";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { useSession } from "@/shared/model/session";

// ponytail: одна страница истории, пагинация нужна, когда у квартиры
// наберётся больше двух лет квитанций
const HISTORY_LIMIT = 24;

/**
 * Начисления квартиры текущей привязки. Ручка отказывает арендатору и
 * неподтверждённому жителю, поэтому для них запрос не уходит: это не ошибка
 * загрузки, а своё состояние экрана
 */
export const useCharges = () => {
  const { currentResidency: residency } = useSession();
  const flatId = residency?.flat_id ?? null;
  const access = (() => {
    if (!residency?.is_connected) {
      return "none";
    }

    // арендатору начисления закрыты при любом состоянии квартиры
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
        query: { limit: HISTORY_LIMIT },
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

  // отказ «уже оплачена» тоже повод перечитать: квитанцию оплатили из
  // другой вкладки или устройства
  const pay = rqClient.useMutation("post", "/api/charges/{charge_id}/pay", {
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["get", "/api/charges/{charge_id}"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["get", "/api/flats/{flat_id}/charges"],
        }),
      ]),
  });

  return {
    card,
    breakdown,
    pay,
    submitPay: () => pay.mutate(options),
  };
};
