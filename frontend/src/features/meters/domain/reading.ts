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

const MILLI = 1000;

export const zonesOf = (meter: Meter): TariffZone[] =>
  meter.tariff_zones === 2 ? ["day", "night"] : ["single"];

export const formatReading = (milli: number): string =>
  (milli / MILLI).toLocaleString("ru-RU", { maximumFractionDigits: 3 });

export const formatAmount = (kopecks: number): string =>
  (kopecks / 100).toLocaleString("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  });

export const formatPeriod = (iso: string): string =>
  new Date(iso)
    .toLocaleDateString("ru-RU", { month: "long", year: "numeric" })
    .replace(" г.", "");

export const parseReading = (input: string): number | null => {
  const normalized = input.replace(/\s/g, "").replace(",", ".");

  if (!/^\d+(\.\d{1,3})?$/.test(normalized)) {
    return null;
  }

  return Math.round(Number(normalized) * MILLI);
};

const TYPICAL_MONTH: Record<MeterType, number> = {
  cold_water: 5,
  hot_water: 3,
  electricity: 200,
  gas: 15,
  heating: 1,
};

const monthsBetween = (from: string, to: string): number => {
  const start = new Date(from);
  const end = new Date(to);

  return (
    (end.getFullYear() - start.getFullYear()) * 12 +
    end.getMonth() -
    start.getMonth()
  );
};

export const isImplausiblyHigh = (
  meter: Meter,
  period: string,
  consumption: number,
): boolean => {
  const since = baselineOf(meter, period).period;
  const months = since ? Math.max(1, monthsBetween(since, period)) : 1;

  return consumption > TYPICAL_MONTH[meter.type] * 10 * months * MILLI;
};

export const baselineOf = (meter: Meter, period: string) =>
  meter.last_period === period
    ? { period: meter.prior_period, values: meter.prior_values }
    : { period: meter.last_period, values: meter.last_values };
