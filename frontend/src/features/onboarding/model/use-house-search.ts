import { useState } from "react";
import { useDebounceState } from "@siberiacancode/reactuse";

import { authParams, rqClient } from "@/shared/api/instance";
import {
  autocompleteStatus,
  type AutocompleteOption,
} from "@/shared/ui/autocomplete";

import type { House } from "./types";

const MIN_QUERY_LENGTH = 3;

export const useHouseSearch = () => {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useDebounceState("", 300);
  const [house, setHouse] = useState<House | null>(null);

  const isSearching =
    !house && debouncedQuery.trim().length >= MIN_QUERY_LENGTH;

  const houses = rqClient.useQuery(
    "get",
    "/api/houses",
    { params: { ...authParams(), query: { q: debouncedQuery } } },
    { enabled: isSearching },
  );

  const found = houses.data?.items ?? [];

  const change = (value: string) => {
    setQuery(value);
    setDebouncedQuery(value);
    setHouse(null);
  };

  const select = (option: AutocompleteOption) => {
    const selected = found.find(({ id }) => id === option.id);

    if (!selected) {
      return;
    }

    setHouse(selected);
    setQuery(selected.address);
    setDebouncedQuery(selected.address);
  };

  return {
    query,
    change,
    select,
    house,
    found,
    status: autocompleteStatus(isSearching, houses.isPending, houses.isError),
    retry: () => void houses.refetch(),
  };
};
