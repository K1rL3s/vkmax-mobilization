import { useState } from "react";
import { useDebounceState } from "@siberiacancode/reactuse";
import { useQuery, type QueryKey } from "@tanstack/react-query";

import { authParams, fetchClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";
import {
  autocompleteStatus,
  type AutocompleteOption,
} from "@/shared/ui/autocomplete";

type SearchConfig<T> = {
  queryKey: QueryKey;
  enabled?: boolean;
  read: (
    query: { q: string; limit: number },
    signal: AbortSignal,
  ) => Promise<{ data?: { items: T[] }; error?: unknown }>;
  option: (item: T) => AutocompleteOption;
  include?: (item: T) => boolean;
};

const useRequestSearch = <T>({
  queryKey,
  enabled = true,
  read,
  option,
  include = () => true,
}: SearchConfig<T>) => {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useDebounceState("", 300);
  const [selected, setSelected] = useState<T | null>(null);
  const searchText = query.trim();
  const isSearching = enabled && selected === null && searchText.length > 0;
  const isDebouncing = searchText !== debouncedQuery;
  const results = useQuery({
    queryKey: [...queryKey, "search", debouncedQuery],
    enabled: isSearching && !isDebouncing,
    retry: false,
    queryFn: async ({ signal }) => {
      const response = await read({ q: debouncedQuery, limit: 20 }, signal);
      if (!response.data) throw response.error;
      return response.data;
    },
  });
  const items = results.data?.items ?? [];
  const isPending = isSearching && (isDebouncing || results.isPending);
  const isReady = isSearching && !isPending && results.data !== undefined;
  const isError = isSearching && !isDebouncing && results.isError;

  const change = (value: string) => {
    setQuery(value);
    setDebouncedQuery(value.trim());
    setSelected(null);
  };

  return {
    query,
    selected,
    options: isReady ? items.filter(include).map(option) : [],
    status: autocompleteStatus(isSearching, isPending, isError),
    change,
    reset: () => change(""),
    select: (id: AutocompleteOption["id"]) => {
      if (!isReady) return;
      const item = items.find(
        (item) => option(item).id === id && include(item),
      );
      if (!item) return;
      setSelected(item);
      setQuery(option(item).title);
      return item;
    },
    retry: () => {
      if (isSearching && !isDebouncing) void results.refetch();
    },
  };
};

export const useRequestHouses = (enabled = true) => {
  const params = orgParams();
  return useRequestSearch({
    queryKey: ["get", "/api/admin/houses", params],
    enabled,
    read: (query, signal) =>
      fetchClient.GET("/api/admin/houses", {
        params: { ...params, query },
        signal,
      }),
    option: (house) => ({ id: house.id, title: house.address }),
  });
};

export const useRequestFlats = (houseId: number) => {
  const params = { ...authParams(), path: { house_id: houseId } };
  return useRequestSearch({
    queryKey: ["get", "/api/houses/{house_id}/flats", params],
    enabled: houseId > 0,
    read: (query, signal) =>
      fetchClient.GET("/api/houses/{house_id}/flats", {
        params: { ...params, query },
        signal,
      }),
    option: (flat) => ({ id: flat.id, title: flat.number }),
  });
};

export const useRequestResidents = (houseId: number, flatId: number) => {
  const params = { ...orgParams(), path: { house_id: houseId } };
  return useRequestSearch({
    queryKey: ["get", "/api/admin/houses/{house_id}/residents", params],
    enabled: houseId > 0,
    read: (query, signal) =>
      fetchClient.GET("/api/admin/houses/{house_id}/residents", {
        params: { ...params, query },
        signal,
      }),
    include: (resident) => {
      const isActive = resident.status === "active";
      const matchesFlat = !flatId || resident.flat_id === flatId;
      return isActive && matchesFlat;
    },
    option: (resident) => ({
      id: resident.resident_id,
      title: resident.name,
      subtitle: resident.flat_number
        ? `Квартира ${resident.flat_number}`
        : "Квартира не указана",
    }),
  });
};
