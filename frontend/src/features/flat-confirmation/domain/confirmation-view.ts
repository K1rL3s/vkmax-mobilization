import type { Residency } from "@/shared/model/session";

export type ConfirmationView =
  "verified" | "no-flat" | "pending" | "rejected" | "ways";

export const confirmationView = (residency: Residency): ConfirmationView => {
  if (residency.verified) {
    return "verified";
  }

  if (residency.flat_id == null) {
    return "no-flat";
  }

  if (residency.verification_status === "pending") {
    return "pending";
  }

  return residency.verification_status === "rejected" ? "rejected" : "ways";
};

export const confirmationCaption = (residency: Residency): string => {
  const view = confirmationView(residency);

  if (view === "no-flat") {
    return residency.flat_number ? "нет в данных УК" : "квартира не выбрана";
  }

  return {
    verified: "квартира подтверждена",
    pending: "запрос на рассмотрении",
    rejected: "УК отклонила запрос",
    ways: "нужно подтвердить",
  }[view];
};
