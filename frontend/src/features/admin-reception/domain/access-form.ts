import type { components } from "@/shared/api/schema/generated";

import { dayKey } from "./day";

export type AccessFlat = { flat_id: number; flat_number: string };

// строка выбора показывает квартиру, а имя подтверждённого жителя - подписью:
// сотрудник узнаёт квартиру по человеку, с которым и договаривается
export type EligibleFlat = AccessFlat & { name: string };

// причина уходит на бэк без ограничения длины, но поле без лимита - это поле,
// в которое однажды вставят весь наряд-заданием
export const accessFormConstraints = {
  reasonMax: 500,
  windowMinutesMin: 15,
  windowMinutesMax: 240,
  perWindowMin: 1,
  perWindowMax: 50,
};

export type WindowsRule = {
  date: string;
  timeFrom: string;
  timeTo: string;
  windowMinutes: number;
};

const pad = (value: number) => String(value).padStart(2, "0");

const minuteOfDay = (time: string) => {
  const [hours, rest] = time.split(":");

  return Number(hours) * 60 + Number(rest);
};

const clock = (total: number) =>
  `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;

// окно уходит наивной локальной строкой: момент без зоны бэк трактует как
// время дома. `Z` не добавляется ни при каких обстоятельствах
export const generateWindows = (rule: WindowsRule): string[] => {
  const from = minuteOfDay(rule.timeFrom);
  const to = minuteOfDay(rule.timeTo);

  if (!rule.date || rule.windowMinutes < 1 || from >= to) {
    return [];
  }

  const starts: string[] = [];

  for (
    let start = from;
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

// предикат бэка - `verified_at is not null AND status != blocked`: ячейку в
// сборе получает только такая квартира, и клиент фильтрует ровно так же,
// иначе выбранная квартира молча окажется среди тех, кому не досталось ячейки
export const eligibleFlats = (
  residents: components["schemas"]["HouseResidentItem"][],
): EligibleFlat[] => {
  const flats = new Map<number, EligibleFlat>();

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

export const isPastDay = (date: string): boolean => date < dayKey(new Date());
