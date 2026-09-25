import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import { dateFrom, type PeriodDays } from "../domain/period";

export const useChannels = (period: PeriodDays) => {
  const channels = rqClient.useQuery("get", "/api/admin/analytics/channels", {
    params: { ...orgParams(), query: { date_from: dateFrom(period) } },
  });

  return {
    isPending: channels.isPending,
    isError: channels.isError,
    retry: () => void channels.refetch(),
    isEmpty: channels.data?.is_empty ?? false,
    items: channels.data?.items ?? [],
  };
};
