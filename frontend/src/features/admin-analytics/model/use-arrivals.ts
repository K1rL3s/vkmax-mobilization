import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import { dateFrom, type PeriodDays } from "../domain/period";

export const useArrivals = (period: PeriodDays) =>
  rqClient.useQuery("get", "/api/admin/analytics/arrivals", {
    params: { ...orgParams(), query: { date_from: dateFrom(period) } },
  });
