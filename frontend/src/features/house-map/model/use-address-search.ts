import { useState } from "react";
import { useDebounceState } from "@siberiacancode/reactuse";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import {
  autocompleteStatus,
  type AutocompleteOption,
} from "@/shared/ui/autocomplete";
import { houseOutlineIcon } from "@/shared/ui/icon";

type House = components["schemas"]["HouseListItem"];

export const useAddressSearch = (onChoose: (house: House) => void) => {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useDebounceState("", 300);
  const [isChosen, setChosen] = useState(false);

  const isSearching = !isChosen && debouncedQuery.trim().length >= 3;

  const houses = rqClient.useQuery(
    "get",
    "/api/houses",
    { params: { ...authParams(), query: { q: debouncedQuery } } },
    { enabled: isSearching },
  );

  const found = houses.data?.items ?? [];

  return {
    query,
    change: (value: string) => {
      setQuery(value);
      setDebouncedQuery(value);
      setChosen(false);
    },
    options: found.map((house): AutocompleteOption => ({
      id: house.id,
      title: house.address,
      subtitle: house.city,
      icon: houseOutlineIcon,
    })),
    select: (option: AutocompleteOption) => {
      const house = found.find(({ id }) => id === option.id);

      if (!house) {
        return;
      }

      setQuery(house.address);
      setChosen(true);
      onChoose(house);
    },
    status: autocompleteStatus(isSearching, houses.isPending, houses.isError),
    retry: () => void houses.refetch(),
  };
};
