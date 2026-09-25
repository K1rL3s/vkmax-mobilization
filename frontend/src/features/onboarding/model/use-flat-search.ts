import { useState } from "react";
import { useDebounceState } from "@siberiacancode/reactuse";

import { authParams, rqClient } from "@/shared/api/instance";
import {
  autocompleteStatus,
  type AutocompleteOption,
} from "@/shared/ui/autocomplete";

import type { Flat, House } from "./types";

export const useFlatSearch = (house: House | null) => {
  const [number, setNumber] = useState("");
  const [debouncedNumber, setDebouncedNumber] = useDebounceState("", 300);
  const [flat, setFlat] = useState<Flat | null>(null);
  const [isManual, setIsManual] = useState(false);

  const isSearching =
    house !== null && !isManual && !flat && debouncedNumber.length > 0;

  const flats = rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/flats",
    {
      params: {
        ...authParams(),
        path: { house_id: house?.id ?? 0 },
        query: { q: debouncedNumber },
      },
    },
    { enabled: isSearching },
  );

  const found = flats.data?.items ?? [];

  const change = (value: string) => {
    setNumber(value);
    setDebouncedNumber(value);
    setFlat(null);
  };

  const select = (option: AutocompleteOption) =>
    setFlat(found.find(({ id }) => id === option.id) ?? null);

  const reset = () => {
    setNumber("");
    setDebouncedNumber("");
    setFlat(null);
    setIsManual(false);
  };

  return {
    value: flat ? flat.number : number,
    change,
    select,
    reset,
    flat,
    number: number.trim(),
    found,
    enableManual: () => setIsManual(true),
    emptyTitle: `В доме нет квартиры ${debouncedNumber}`,
    status: autocompleteStatus(isSearching, flats.isPending, flats.isError),
    retry: () => void flats.refetch(),
  };
};
