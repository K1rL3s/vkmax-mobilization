import type { components } from "@/shared/api/schema/generated";

export type Meter = components["schemas"]["MeterItem"];

export type MeterType = components["schemas"]["MeterType"];

export type TariffZone = components["schemas"]["TariffZone"];

export type ReadingPeriod = components["schemas"]["ReadingPeriodItem"];

export type ReadingResult = components["schemas"]["SubmitReadingResponse"];

export const METER_LABEL: Record<MeterType, string> = {
  cold_water: "Холодная вода",
  hot_water: "Горячая вода",
  electricity: "Электричество",
  gas: "Газ",
  heating: "Отопление",
};

export const METER_UNIT: Record<MeterType, string> = {
  cold_water: "м³",
  hot_water: "м³",
  electricity: "кВт·ч",
  gas: "м³",
  heating: "Гкал",
};

export const ZONE_LABEL: Record<TariffZone, string> = {
  single: "Показание",
  day: "День",
  night: "Ночь",
};

// контракт держит показания и расход в тысячных долях единицы измерения
const MILLI = 1000;

const readingFormat = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 3,
});

const amountFormat = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

const periodFormat = new Intl.DateTimeFormat("ru-RU", {
  month: "long",
  year: "numeric",
});

/** Зоны счётчика в том порядке, в котором житель видит их на приборе. */
export const zonesOf = (meter: Meter): TariffZone[] =>
  meter.tariff_zones === 2 ? ["day", "night"] : ["single"];

export const formatReading = (milli: number): string =>
  readingFormat.format(milli / MILLI);

export const formatAmount = (kopecks: number): string =>
  amountFormat.format(kopecks / 100);

// Intl всегда приписывает к месяцу с годом «г.», а в макете её нет
export const formatPeriod = (iso: string): string =>
  periodFormat.format(new Date(iso)).replace(" г.", "");

/**
 * Разбирает введённое показание в тысячные доли. `null` - значение, с которым
 * счётчик нельзя отправить: пустое, с буквами или с лишними знаками после
 * запятой.
 */
export const parseReading = (input: string): number | null => {
  const normalized = input.replace(/\s/g, "").replace(",", ".");

  if (!/^\d+(\.\d{1,3})?$/.test(normalized)) {
    return null;
  }

  return Math.round(Number(normalized) * MILLI);
};
