import { rqClient } from "@/shared/api/instance";
import { nextOffset } from "@/shared/api/next-offset";
import { houseParams } from "@/shared/model/session";

export const useAnnouncements = () => {
  const query = rqClient.useInfiniteQuery(
    "get",
    "/api/announcements",
    { params: { ...houseParams(), query: { limit: 20 } } },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: nextOffset,
    },
  );

  return {
    items: query.data?.pages.flatMap((page) => page.items) ?? [],
    isPending: query.isPending,
    isError: query.isError,
    error: query.error,
    hasMore: query.hasNextPage,
    isLoadingMore: query.isFetchingNextPage,
    retry: () => void query.refetch(),
    loadMore: () => void query.fetchNextPage(),
  };
};
