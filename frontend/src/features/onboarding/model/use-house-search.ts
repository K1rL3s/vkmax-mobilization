import { useState } from "react";
import { useDebounceState } from "@siberiacancode/reactuse";

import { authParams, rqClient } from "@/shared/api/instance";
import {
  autocompleteStatus,
  type AutocompleteOption,
} from "@/shared/ui/autocomplete";

import type { House } from "./types";

export const useHouseSearch = (initial: House | null) => {
  const [query, setQuery] = useState(initial?.address ?? "");
  const [debouncedQuery, setDebouncedQuery] = useDebounceState(
    initial?.address ?? "",
    300,
  );
  const [house, setHouse] = useState<House | null>(initial);

  const isSearching = !house && debouncedQuery.trim().length >= 3;

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

    pick(selected);
  };

  const pick = (selected: House) => {
    setHouse(selected);
    setQuery(selected.address);
    setDebouncedQuery(selected.address);
  };

  return {
    query,
    change,
    select,
    pick,
    house,
    found,
    status: autocompleteStatus(isSearching, houses.isPending, houses.isError),
    retry: () => void houses.refetch(),
  };
};
