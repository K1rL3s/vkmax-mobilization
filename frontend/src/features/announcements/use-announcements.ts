import { rqClient } from "@/shared/api/instance";
import { nextOffset } from "@/shared/api/next-offset";
import { houseParams } from "@/shared/model/session";

export const useAnnouncements = (archived: boolean) => {
  const query = rqClient.useInfiniteQuery(
    "get",
    "/api/announcements",
    { params: { ...houseParams(), query: { limit: 20, archived } } },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: nextOffset,
    },
  );

  return {
    items: query.data?.pages.flatMap((page) => page.items) ?? [],
    archiveTotal: query.data?.pages[0]?.archive_total ?? 0,
    isPending: query.isPending,
    isError: query.isError,
    error: query.error,
    hasMore: query.hasNextPage,
    isLoadingMore: query.isFetchingNextPage,
    retry: () => void query.refetch(),
    loadMore: () => void query.fetchNextPage(),
  };
};
