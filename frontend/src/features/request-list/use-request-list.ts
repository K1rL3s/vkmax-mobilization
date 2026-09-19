import { useState } from "react";

import { rqClient } from "@/shared/api/instance";
import { houseParams } from "@/shared/model/session";

import { groupRequests, type FilterId } from "./filters";

// лента грузится одной пачкой: фильтр и группы считаются на клиенте, а
// серверная пагинация разрезала бы их посередине
const PAGE_LIMIT = 100;

export const useRequestList = () => {
  const [filter, setFilter] = useState<FilterId>("all");

  const requests = rqClient.useQuery("get", "/api/requests", {
    params: { ...houseParams(), query: { limit: PAGE_LIMIT } },
  });

  const items = requests.data?.items ?? [];

  return {
    filter,
    setFilter,
    isPending: requests.isPending,
    isError: requests.isError,
    retry: () => void requests.refetch(),
    isEmpty: items.length === 0,
    groups: groupRequests(items, filter),
  };
};
