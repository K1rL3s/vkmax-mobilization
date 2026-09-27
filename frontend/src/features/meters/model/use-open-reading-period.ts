import type { ReadingPeriod } from "../domain/reading";

import { useFlatReadings } from "./use-flat-readings";

export const useOpenReadingPeriod = (): ReadingPeriod | null => {
  const { meters, periods } = useFlatReadings();

  if (meters.length === 0) {
    return null;
  }

  return (
    periods.find((period) => period.is_open && !period.is_submitted) ?? null
  );
};
