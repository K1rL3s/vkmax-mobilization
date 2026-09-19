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

/**
 * Нормативный срок словами: сколько осталось или насколько заявка просрочена.
 * Срока может не быть - категория задаёт его не всегда.
 */
export const deadlineLeft = (
  deadlineAt: string | null | undefined,
  now = Date.now(),
) => {
  if (!deadlineAt) {
    return null;
  }

  const left = new Date(deadlineAt).getTime() - now;

  if (Number.isNaN(left)) {
    return null;
  }

  return left >= 0
    ? { overdue: false, text: `Осталось ${duration(left)}` }
    : { overdue: true, text: `Просрочена на ${duration(-left)}` };
};

/**
 * Доля нормативного срока, которая уже прошла: 0 - заявку только подали,
 * 1 - срок вышел. Из неё рисуется полоса на Главной.
 */
export const deadlineProgress = (
  createdAt: string,
  deadlineAt: string | null | undefined,
  now = Date.now(),
) => {
  if (!deadlineAt) {
    return null;
  }

  const start = new Date(createdAt).getTime();
  const end = new Date(deadlineAt).getTime();

  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) {
    return null;
  }

  return Math.min(1, Math.max(0, (now - start) / (end - start)));
};
