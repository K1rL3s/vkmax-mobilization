const MINUTE = 60 * 1000;

const HOUR = 60 * MINUTE;

const DAY = 24 * HOUR;

const dayFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
});

const timeFormat = new Intl.DateTimeFormat("ru-RU", {
  hour: "2-digit",
  minute: "2-digit",
});

export const formatDay = (iso: string) => dayFormat.format(new Date(iso));

export const formatTime = (iso: string) => timeFormat.format(new Date(iso));

export const formatDayTime = (iso: string) =>
  `${formatDay(iso)}, ${formatTime(iso)}`;

export const formatArea = (area: number) =>
  `${(area / 100).toLocaleString("ru-RU", { maximumFractionDigits: 2 })} м²`;

export const formatPercent = (percent: number) =>
  `${(percent / 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;

export const plural = (
  count: number,
  [one, few, many]: [string, string, string],
) => {
  const tens = count % 100;
  const units = count % 10;

  if (tens > 10 && tens < 20) {
    return many;
  }

  if (units === 1) {
    return one;
  }

  return units > 1 && units < 5 ? few : many;
};

export const duration = (ms: number) => {
  if (ms >= DAY) {
    const days = Math.floor(ms / DAY);

    return `${days} ${plural(days, ["день", "дня", "дней"])}`;
  }

  if (ms >= HOUR) {
    const hours = Math.floor(ms / HOUR);
    const minutes = Math.floor((ms % HOUR) / MINUTE);

    return minutes === 0 ? `${hours} ч` : `${hours} ч ${minutes} мин`;
  }

  return `${Math.max(1, Math.floor(ms / MINUTE))} мин`;
};
