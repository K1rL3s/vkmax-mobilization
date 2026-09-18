import type { AutocompleteStatus } from "./autocomplete";

export const autocompleteStatus = (
  isSearching: boolean,
  isPending: boolean,
  isError: boolean,
): AutocompleteStatus => {
  if (!isSearching) {
    return "idle";
  }

  if (isError) {
    return "error";
  }

  return isPending ? "loading" : "ready";
};
