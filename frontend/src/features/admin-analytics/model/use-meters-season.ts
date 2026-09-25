import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

export const useMetersSeason = () =>
  rqClient.useQuery("get", "/api/admin/analytics/meters-season", {
    params: orgParams(),
  });
