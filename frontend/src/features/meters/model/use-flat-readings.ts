import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

/**
 * Счётчики квартиры и периоды, за которые можно подать показания. Обе ручки
 * требуют подтверждённой квартиры, поэтому без неё запросы не уходят: отказ
 * доступа здесь не ошибка загрузки, а нормальное состояние экрана.
 */
export const useFlatReadings = () => {
  const { currentResidency: residency } = useSession();
  const flatId = residency?.verified ? (residency.flat_id ?? null) : null;
  const options = {
    params: { ...authParams(), path: { flat_id: flatId ?? 0 } },
  };
  const enabled = flatId !== null;

  const meters = rqClient.useQuery(
    "get",
    "/api/flats/{flat_id}/meters",
    options,
    { enabled },
  );

  const periods = rqClient.useQuery(
    "get",
    "/api/flats/{flat_id}/reading-periods",
    options,
    { enabled },
  );

  return {
    residency,
    meters: meters.data ?? [],
    periods: periods.data ?? [],
    isPending: enabled && (meters.isPending || periods.isPending),
    isError: meters.isError || periods.isError,
    refetch: () => {
      void meters.refetch();
      void periods.refetch();
    },
  };
};
