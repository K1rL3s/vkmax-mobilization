import type { Residency } from "@/shared/model/session";

import { confirmationView } from "../domain/confirmation-view";

import { useResidency } from "./use-residency";

const flatAddress = (residency: Residency): string => {
  if (!residency.flat_number) {
    return residency.address;
  }

  return `${residency.address}, кв. ${residency.flat_number}`;
};

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
    address: flatAddress(residency),
  };
};
