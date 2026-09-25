import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import { dateFrom, type PeriodDays } from "../domain/period";

export const useExecutors = (period: PeriodDays) => {
  const executors = rqClient.useQuery("get", "/api/admin/analytics/executors", {
    params: { ...orgParams(), query: { date_from: dateFrom(period) } },
  });

  return {
    isPending: executors.isPending,
    isError: executors.isError,
    retry: () => void executors.refetch(),
    // своего `is_empty` у ручки нет: пусто - это пустой список
    isEmpty: (executors.data?.length ?? 0) === 0,
    items: executors.data ?? [],
  };
};
