import { confirmationView } from "../domain/confirmation-view";

import { useResidency } from "./use-residency";

export const useFlatConfirmation = () => {
  const { residency, returnTo, exit } = useResidency();

  if (!residency) {
    return { residency: null };
  }

  return {
    residency,
    returnTo,
    exit,
    view: confirmationView(residency),
    address: residency.flat_number
      ? `${residency.address}, кв. ${residency.flat_number}`
      : residency.address,
  };
};
