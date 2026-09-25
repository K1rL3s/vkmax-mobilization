import { formatPeriod } from "../domain/reading";

import { useFlatReadings } from "./use-flat-readings";

export const useReadingsHint = (): string | null => {
  const { residency, meters, periods, isPending, isError } = useFlatReadings();

  if (residency && !residency.verified) {
    return "Подтвердите квартиру, чтобы подавать показания";
  }

  if (isPending || isError) {
    return null;
  }

  if (meters.length === 0) {
    return "Счётчики квартиры заводит УК";
  }

  const open = periods.find((period) => period.is_open);

  if (!open) {
    return "Окно подачи закрыто";
  }

  return open.is_submitted
    ? `Показания за ${formatPeriod(open.period)} отправлены`
    : `Окно открыто · ${formatPeriod(open.period)}`;
};
