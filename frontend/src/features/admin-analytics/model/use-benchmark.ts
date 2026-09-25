import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

export const useBenchmark = () =>
  rqClient.useQuery("get", "/api/admin/analytics/benchmark", {
    params: orgParams(),
  });
