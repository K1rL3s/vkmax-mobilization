import { useState } from "react";

import { rqClient } from "@/shared/api/instance";
import { houseParams } from "@/shared/model/session";

import { groupRequests, type FilterId } from "./filters";

export const useRequestList = () => {
  const [filter, setFilter] = useState<FilterId>("all");

  const requests = rqClient.useQuery("get", "/api/requests", {
    params: { ...houseParams(), query: { limit: 100 } },
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
