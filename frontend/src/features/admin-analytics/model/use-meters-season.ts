import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

export const useMetersSeason = () => {
  const season = rqClient.useQuery(
    "get",
    "/api/admin/analytics/meters-season",
    { params: orgParams() },
  );

  return {
    isPending: season.isPending,
    isError: season.isError,
    retry: () => void season.refetch(),
    isEmpty: season.data?.is_empty ?? false,
    season: season.data ?? null,
  };
};
