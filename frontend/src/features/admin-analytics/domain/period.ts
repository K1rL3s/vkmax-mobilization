export type PeriodDays = 30 | 90;

export const PERIODS: PeriodDays[] = [30, 90];

export const dateFrom = (days: PeriodDays): string =>
  new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
