import type { components } from "@/shared/api/schema/generated";

type ChargeItem = components["schemas"]["ChargeListItem"];

export type ChargeCard = components["schemas"]["ChargeCard"];

export type ChargeBreakdown = components["schemas"]["ChargeBreakdown"];

type ServiceType = components["schemas"]["ServiceType"];

export type ServiceConsumption = components["schemas"]["ServiceConsumption"];

export const SERVICE_UNIT: Partial<Record<ServiceType, string>> = {
  cold_water: "м³",
  hot_water: "м³",
  electricity: "кВт·ч",
  gas: "м³",
  heating: "Гкал",
};

export const SERVICE_LABEL: Record<ServiceType, string> = {
  cold_water: "Холодная вода",
  hot_water: "Горячая вода",
  electricity: "Электроэнергия",
  gas: "Газ",
  heating: "Отопление",
  maintenance: "Содержание жилья",
  overhaul: "Капитальный ремонт",
  waste: "Обращение с ТКО",
  penalty: "Пени",
  recalculation: "Перерасчёт",
};

const MONTH_DATIVE = [
  "январю",
  "февралю",
  "марту",
  "апрелю",
  "маю",
  "июню",
  "июлю",
  "августу",
  "сентябрю",
  "октябрю",
  "ноябрю",
  "декабрю",
];

const periodFormat = new Intl.DateTimeFormat("ru-RU", {
  month: "long",
  year: "numeric",
});

const monthFormat = new Intl.DateTimeFormat("ru-RU", { month: "short" });

const parsePeriod = (iso: string) => {
  const [year, month] = iso.split("-").map(Number);

  return new Date(year ?? 0, (month ?? 1) - 1, 1);
};

export const formatPeriod = (iso: string): string => {
  const text = periodFormat.format(parsePeriod(iso)).replace(" г.", "");

  return text.charAt(0).toUpperCase() + text.slice(1);
};

export const formatMonth = (iso: string): string =>
  monthFormat.format(parsePeriod(iso)).replace(".", "");

export const toMonthDative = (iso: string): string =>
  MONTH_DATIVE[parsePeriod(iso).getMonth()] ?? "";

const isPreviousMonth = (previous: string, current: string) => {
  const date = parsePeriod(current);
  date.setMonth(date.getMonth() - 1);

  return parsePeriod(previous).getTime() === date.getTime();
};

export const formatMoney = (kopecks: number, signed = false): string =>
  new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: kopecks % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(kopecks / 100);

export const formatVolume = (milli: number): string =>
  (milli / 1000).toLocaleString("ru-RU", { maximumFractionDigits: 3 });

export const formatTariff = (tariff: number): string =>
  new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(tariff / 10000);

export const listDelta = (
  item: ChargeItem,
  previous: ChargeItem | undefined,
): string | null =>
  previous && isPreviousMonth(previous.period, item.period)
    ? `${formatMoney(item.total - previous.total, true)} к ${toMonthDative(previous.period)}`
    : null;
