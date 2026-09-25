import type { components } from "@/shared/api/schema/generated";

type MetricUnit = components["schemas"]["MetricUnit"];

const MINUTES_IN_DAY = 24 * 60;

const formatMinutes = (value: number): string => {
  if (value < 60) {
    return `${value} мин`;
  }

  if (value < MINUTES_IN_DAY) {
    const hours = Math.floor(value / 60);
    const rest = value % 60;

    return rest === 0 ? `${hours} ч` : `${hours} ч ${rest} мин`;
  }

  const days = Math.floor(value / MINUTES_IN_DAY);
  const hours = Math.floor((value % MINUTES_IN_DAY) / 60);

  return hours === 0 ? `${days} дн` : `${days} дн ${hours} ч`;
};

export const formatMetric = (value: number, unit: MetricUnit): string => {
  switch (unit) {
    case "minutes":
      return formatMinutes(value);
    case "percent":
      return value > 0 && value < 100 ? "<1%" : `${Math.round(value / 100)}%`;
    case "points":
      return (value / 100).toFixed(1).replace(".", ",");
    case "kopeck":
      return new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: "RUB",
        maximumFractionDigits: 0,
      }).format(value / 100);
    case "count":
      return String(value);
  }
};
