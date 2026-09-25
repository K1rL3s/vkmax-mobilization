import type { components } from "@/shared/api/schema/generated";

import { minuteOfDay, pad } from "./day";

export type AccessFlat = { flat_id: number; flat_number: string };

export const accessFormConstraints = {
  reasonMax: 500,
  windowMinutesMin: 15,
  windowMinutesMax: 240,
  perWindowMin: 1,
  perWindowMax: 50,
};

const clock = (total: number) =>
  `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;

export const generateWindows = (rule: {
  date: string;
  timeFrom: string;
  timeTo: string;
  windowMinutes: number;
}): string[] => {
  const to = minuteOfDay(rule.timeTo);
  const starts: string[] = [];

  if (!rule.date || rule.windowMinutes < 1) {
    return starts;
  }

  for (
    let start = minuteOfDay(rule.timeFrom);
    start + rule.windowMinutes <= to;
    start += rule.windowMinutes
  ) {
    starts.push(`${rule.date}T${clock(start)}:00`);
  }

  return starts;
};

export const windowLabel = (startsAt: string, minutes: number): string => {
  const from = startsAt.slice(11, 16);

  return `${from}-${clock(minuteOfDay(from) + minutes)}`;
};

export const eligibleFlats = (
  residents: components["schemas"]["HouseResidentItem"][],
) => {
  const flats = new Map<number, AccessFlat & { name: string }>();

  for (const resident of residents) {
    const { flat_id: flatId, flat_number: flatNumber } = resident;
    const isEligible = resident.verified && resident.status !== "blocked";
    const hasFlat = flatId != null && flatNumber != null;

    if (isEligible && hasFlat && !flats.has(flatId)) {
      flats.set(flatId, {
        flat_id: flatId,
        flat_number: flatNumber,
        name: resident.name,
      });
    }
  }

  return [...flats.values()];
};
