import type { AutocompleteOption } from "@/shared/ui/autocomplete";
import { houseOutlineIcon } from "@/shared/ui/icon";

import { useFlatSearch } from "./use-flat-search";
import { useHouseLink } from "./use-house-link";
import { useHouseSearch } from "./use-house-search";

export const useHouseSelect = () => {
  const houseSearch = useHouseSearch();
  const flatSearch = useFlatSearch(houseSearch.house);
  const link = useHouseLink();

  const { house } = houseSearch;
  const isAlreadyLinked =
    house !== null && link.isLinked(house.id) && !link.isLinking;
  const isFlatChosen = flatSearch.flat !== null || flatSearch.number !== "";

  return {
    query: houseSearch.query,
    changeQuery: houseSearch.change,
    houseOptions: houseSearch.found.map((found) => ({
      id: found.id,
      title: found.address,
      subtitle: link.isLinked(found.id)
        ? "Вы уже привязаны к этому дому"
        : found.city,
      icon: houseOutlineIcon,
    })),
    housesStatus: houseSearch.status,
    retryHouses: houseSearch.retry,
    selectHouse: (option: AutocompleteOption) => {
      houseSearch.select(option);
      flatSearch.reset();
    },

    flatValue: flatSearch.value,
    changeFlatQuery: flatSearch.change,
    flatOptions: flatSearch.found.map((found) => ({
      id: found.id,
      title: `Квартира ${found.number}`,
      subtitle:
        found.entrance == null ? undefined : `${found.entrance}-й подъезд`,
      icon: houseOutlineIcon,
    })),
    flatsStatus: flatSearch.status,
    retryFlats: flatSearch.retry,
    selectFlat: flatSearch.select,
    isFlatDisabled: house === null,
    emptyFlatTitle: flatSearch.emptyTitle,
    enableManualFlat: flatSearch.enableManual,

    isAlreadyLinked,
    isLinking: link.isLinking,
    isLinkFailed: link.isFailed,
    isSubmitDisabled: house === null || isAlreadyLinked || !isFlatChosen,
    submit: () => {
      if (house) {
        link.submit(house, flatSearch.flat, flatSearch.number);
      }
    },
  };
};
