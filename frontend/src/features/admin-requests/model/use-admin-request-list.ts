import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import {
  CATEGORY_ICON,
  useRequestCategories,
  type RequestCategory,
} from "@/features/request";
import { isForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

import {
  FILTERS,
  matchesFilter,
  toSections,
  type FilterId,
} from "../domain/request-filters";

const PAGE_SIZE = 100;

const filterSchema = z.object({
  filter: z
    .custom<FilterId>((value) => FILTERS.some(({ id }) => id === value))
    .catch("all"),
  category: z
    .custom<RequestCategory>(
      (value) =>
        typeof value === "string" && Object.hasOwn(CATEGORY_ICON, value),
    )
    .optional()
    .catch(undefined),
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
        query: { limit: PAGE_SIZE, grouped: true },
      },
    },
    { retry: (count, error) => !isForbidden(error) && count < 3 },
  );

  const updateFilter = (name: "filter" | "category", value: string) => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value && value !== "all") next.set(name, value);
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
    isSuccess: requests.isSuccess,
    hasFilters: filters.filter !== "all" || !!filters.category,
    updateFilter,
    clearFilters: () => setSearchParams({}, { replace: true }),
    retry: () => {
      void requests.refetch();
      void categories.refetch();
    },
  };
};
