import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import {
  useRequestCategories,
  type RequestCategory,
  type RequestPlace,
} from "@/features/request";
import { isForbidden, retryUnlessForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import {
  FILTERS,
  matchesFilter,
  toSections,
  type FilterId,
} from "../domain/request-filters";
import { isCategory } from "../domain/request-workflow";

const PAGE_SIZE = 100;

export const SORTS = [
  { id: "important", label: "Сначала важные" },
  { id: "deadline", label: "По сроку" },
  { id: "massive", label: "Массовые" },
  { id: "fresh", label: "Свежие" },
] as const;

type SortId = (typeof SORTS)[number]["id"];

const filterSchema = z.object({
  filter: z
    .custom<FilterId>((value) => FILTERS.some(({ id }) => id === value))
    .catch("all"),
  category: z.custom<RequestCategory>(isCategory).optional().catch(undefined),
  house: z.coerce.number().int().positive().optional().catch(undefined),
  place: z
    .enum(["flat", "house"] satisfies RequestPlace[])
    .optional()
    .catch(undefined),
  sort: z
    .custom<SortId>((value) => SORTS.some(({ id }) => id === value))
    .catch("important"),
});

export const useAdminRequestList = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filterSchema.parse(Object.fromEntries(searchParams));
  const categories = useRequestCategories();
  const requests = rqClient.useQuery(
    "get",
    "/api/admin/requests",
    {
      params: {
        ...orgParams(),
        query: {
          limit: PAGE_SIZE,
          grouped: true,
          house_id: filters.house,
          place: filters.place,
          sort: filters.sort,
        },
      },
    },
    { retry: retryUnlessForbidden },
  );

  const updateFilter = (
    name: "filter" | "category" | "house" | "place" | "sort",
    value: string,
  ) => {
    const isDefault = name === "sort" ? value === "important" : value === "all";
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (!isDefault) next.set(name, value);
        else next.delete(name);
        return next;
      },
      { replace: true },
    );
  };

  const items = (requests.data?.items ?? []).filter(
    (request) =>
      matchesFilter(request, filters.filter) &&
      (!filters.category || request.category === filters.category),
  );
  const total = requests.data?.total ?? 0;

  return {
    filters,
    categories: categories.data ?? [],
    sections: toSections(items),
    isClipped: total > PAGE_SIZE,
    total,
    isForbidden: isForbidden(requests.error),
    isPending: requests.isPending,
    isError: requests.isError,
    loadError: requests.error,
    isSuccess: requests.isSuccess,
    hasFilters:
      filters.filter !== "all" ||
      !!filters.category ||
      !!filters.house ||
      !!filters.place,
    houseAddress: requests.data?.items[0]?.address,
    updateFilter,
    clearFilters: () => setSearchParams({}, { replace: true }),
    retry: () => {
      void requests.refetch();
      void categories.refetch();
    },
  };
};
