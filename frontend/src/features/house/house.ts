import { useQuery } from "@tanstack/react-query";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type HouseCard = components["schemas"]["HouseCard"];

const houseCardQueryOptions = (houseId: number) =>
  rqClient.queryOptions("get", "/api/houses/{house_id}", {
    params: { ...authParams(), path: { house_id: houseId } },
  });

export const loadHouseCard = (houseId: number) =>
  queryClient.query({ ...houseCardQueryOptions(houseId), staleTime: "static" });

export const useHouseCard = (houseId: number | undefined) =>
  useQuery({
    ...houseCardQueryOptions(houseId ?? 0),
    enabled: houseId !== undefined,
  });
