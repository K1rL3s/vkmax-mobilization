import { findHouse } from "./houses";

export const DAY = 24 * 60 * 60 * 1000;
export const MINUTE = 60 * 1000;

// бэк отдаёт слоты на две недели вперёд от сегодняшнего дня
export const HORIZON_DAYS = 14;

// часы приёма заданы в поясе УК (у мок-организаций это Москва, UTC+3 без
// перехода на летнее время), а не в поясе машины, где запущен мок. День здесь -
// полночь UTC московской даты, момент - сдвиг от неё
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

// контракт нумерует дни с понедельника, `Date` - с воскресенья
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

// наивную строку окна доступа бэк трактует как время дома (`house.to_utc()`),
// поэтому мок обязан сделать то же: иначе житель видит окно, сдвинутое на
// разницу поясов, и сквозной сценарий врёт ровно там, где его и проверяют
export const fromOrgNaive = (value: string): string =>
  /(Z|[+-]\d{2}:\d{2})$/.test(value)
    ? new Date(value).toISOString()
    : new Date(
        Date.parse(`${value}Z`) - ORG_OFFSET_MINUTES * MINUTE,
      ).toISOString();

export const orgOf = (houseId: number): number | null =>
  findHouse(houseId)?.org?.id ?? null;
