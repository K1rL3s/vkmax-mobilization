export const period = (monthsBack: number): string => {
  const today = new Date();
  const month = new Date(today.getFullYear(), today.getMonth() - monthsBack, 1);

  return `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-01`;
};

export const minutes = (count: number) =>
  new Date(Date.now() + count * 60 * 1000).toISOString();

export const hours = (count: number) => minutes(count * 60);

export const days = (count: number) => minutes(count * 24 * 60);

export const shift = (iso: string, addMinutes: number) =>
  new Date(new Date(iso).getTime() + addMinutes * 60 * 1000).toISOString();

export const today = (): string => new Date().toISOString().slice(0, 10);

export const DAY = 24 * 60 * 60 * 1000;

const MINUTE = 60 * 1000;

const ORG_OFFSET_MINUTES = 3 * 60;

export const startOfToday = (): Date => {
  const today = new Date(Date.now() + ORG_OFFSET_MINUTES * MINUTE);
  today.setUTCHours(0, 0, 0, 0);

  return today;
};

export const isoDate = (day: Date): string => day.toISOString().slice(0, 10);

export const todayIso = (): string => isoDate(startOfToday());

export const moment = (day: Date, minute: number): Date =>
  new Date(day.getTime() + (minute - ORG_OFFSET_MINUTES) * MINUTE);

export const at = (day: Date, hours: number, minutes = 0): string =>
  moment(day, hours * 60 + minutes).toISOString();

export const weekdayOf = (day: Date): number => (day.getUTCDay() + 6) % 7;

export const minuteOfDay = (time: string): number => {
  const [hours, minutes] = time.split(":");

  return Number(hours) * 60 + Number(minutes);
};

export const weekdayAfter = (offset: number): Date => {
  const day = new Date(startOfToday().getTime() + offset * DAY);

  while (weekdayOf(day) > 4) {
    day.setUTCDate(day.getUTCDate() + 1);
  }

  return day;
};

export const fromOrgNaive = (value: string): string =>
  /(Z|[+-]\d{2}:\d{2})$/.test(value)
    ? new Date(value).toISOString()
    : new Date(
        Date.parse(`${value}Z`) - ORG_OFFSET_MINUTES * MINUTE,
      ).toISOString();
