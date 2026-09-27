import type { Residency } from "@/shared/model/session";

export type ConfirmationView =
  "verified" | "no-flat" | "flat-missing" | "pending" | "rejected" | "ways";

export type ResidencyState = ConfirmationView | "not-connected";

export const confirmationView = (residency: Residency): ConfirmationView => {
  if (residency.verified) {
    return "verified";
  }

  if (residency.flat_id == null) {
    return residency.flat_number ? "flat-missing" : "no-flat";
  }

  if (residency.verification_status === "pending") {
    return "pending";
  }

  return residency.verification_status === "rejected" ? "rejected" : "ways";
};

export const residencyState = (residency: Residency): ResidencyState =>
  residency.is_connected ? confirmationView(residency) : "not-connected";

export const confirmationCaption = (state: ResidencyState): string =>
  ({
    verified: "квартира подтверждена",
    pending: "запрос на рассмотрении",
    rejected: "УК отклонила запрос",
    ways: "нужно подтвердить",
    "no-flat": "квартира не выбрана",
    "flat-missing": "нет в данных УК",
    "not-connected": "дом ещё не подключён к сервису",
  })[state];
