import { useState } from "react";
import { keepPreviousData } from "@tanstack/react-query";

import { rqClient } from "@/shared/api/instance";
import { nextOffset } from "@/shared/api/next-offset";
import { orgParams } from "@/shared/model/session";

export const useHouseReadings = (houseId: number) => {
  const [onlyBelow, setOnlyBelow] = useState(false);

  const readings = rqClient.useInfiniteQuery(
    "get",
    "/api/admin/houses/{house_id}/readings",
    {
      params: {
        ...orgParams(),
        path: { house_id: houseId },
        query: { only_below_previous: onlyBelow, limit: 10 },
      },
    },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: nextOffset,
      placeholderData: keepPreviousData,
    },
  );

  return {
    onlyBelow,
    setOnlyBelow,
    items: readings.data?.pages.flatMap((page) => page.items) ?? [],
    isPending: readings.isPending,
    isError: readings.isError,
    loadError: readings.error,
    retry: () => void readings.refetch(),
    hasMore: readings.hasNextPage,
    isLoadingMore: readings.isFetchingNextPage,
    loadMore: () => void readings.fetchNextPage(),
  };
};
