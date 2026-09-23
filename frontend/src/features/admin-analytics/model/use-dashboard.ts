import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import { dateFrom, type PeriodDays } from "../domain/period";
import { splitTiles } from "../domain/tile";

export const useDashboard = (period: PeriodDays) => {
  const dashboard = rqClient.useQuery("get", "/api/admin/analytics/dashboard", {
    params: { ...orgParams(), query: { date_from: dateFrom(period) } },
  });

  const tiles = splitTiles(dashboard.data?.tiles ?? []);

  return {
    isPending: dashboard.isPending,
    isError: dashboard.isError,
    retry: () => void dashboard.refetch(),
    isEmpty: dashboard.data?.is_empty ?? false,
    nowTiles: tiles.now,
    periodTiles: tiles.period,
    charts: dashboard.data?.charts ?? [],
  };
};
