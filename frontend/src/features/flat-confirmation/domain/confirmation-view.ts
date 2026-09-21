import type { Residency } from "@/shared/model/session";

export type ConfirmationView =
  "verified" | "no-flat" | "pending" | "rejected" | "ways";

// порядок проверок неслучаен: подтверждение живет отдельно от запроса в УК, и
// у жителя, сверившего лицевой счет при живом запросе, статус так и остается
// pending - смотреть на него раньше verified значит спрятать подтверждение
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

// вторая строка адресного блока: одна формулировка на Главной, в списке
// привязок и в карточке квартиры
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
