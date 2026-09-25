import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import { splitRegions } from "../domain/benchmark";

export const useBenchmark = () => {
  const benchmark = rqClient.useQuery("get", "/api/admin/analytics/benchmark", {
    params: orgParams(),
  });

  const rows = splitRegions(benchmark.data?.regions ?? []);

  return {
    isPending: benchmark.isPending,
    isError: benchmark.isError,
    retry: () => void benchmark.refetch(),
    isEmpty: benchmark.data?.is_empty ?? false,
    metrics: benchmark.data?.metrics ?? [],
    regions: rows.regions,
    cities: rows.cities,
    houses: benchmark.data?.unconnected_houses ?? [],
  };
};
