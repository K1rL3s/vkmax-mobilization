export const PERIODS = [
  { days: 7, label: "7 дней", title: "За 7 дней" },
  { days: 30, label: "30 дней", title: "За 30 дней" },
  { days: 90, label: "90 дней", title: "За 90 дней" },
  { days: 182, label: "Полгода", title: "За полгода" },
  { days: 365, label: "Год", title: "За год" },
] as const;

export type PeriodDays = (typeof PERIODS)[number]["days"];

export const dateFrom = (days: PeriodDays): string =>
  new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
