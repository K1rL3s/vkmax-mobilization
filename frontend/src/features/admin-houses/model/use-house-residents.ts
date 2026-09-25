import { useState } from "react";
import { useDebounceValue } from "@siberiacancode/reactuse";
import { keepPreviousData } from "@tanstack/react-query";

import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import { nextOffset } from "./next-offset";

// размер страницы - аргумент: карточке дома хватает десятки, выбору квартир
// в сборе доступа нужна полусотня, иначе «Показать ещё» жмут весь дом
export const useHouseResidents = (houseId: number, limit = 10) => {
  const [query, setQuery] = useState("");
  const search = useDebounceValue(query.trim(), 300);

  const residents = rqClient.useInfiniteQuery(
    "get",
    "/api/admin/houses/{house_id}/residents",
    {
      params: {
        ...orgParams(),
        path: { house_id: houseId },
        query: { q: search || undefined, limit },
      },
    },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: nextOffset,
      // поиск не сбрасывает список в загрузку на каждую букву
      placeholderData: keepPreviousData,
    },
  );

  return {
    query,
    setQuery,
    isSearching: search !== "",
    items: residents.data?.pages.flatMap((page) => page.items) ?? [],
    total: residents.data?.pages[0]?.total ?? 0,
    isPending: residents.isPending,
    isError: residents.isError,
    retry: () => void residents.refetch(),
    hasMore: residents.hasNextPage,
    isLoadingMore: residents.isFetchingNextPage,
    loadMore: () => void residents.fetchNextPage(),
  };
};
