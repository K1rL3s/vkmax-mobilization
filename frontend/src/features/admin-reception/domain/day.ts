// день приёма - календарная дата в поясе устройства: пояса организации в
// админском контракте нет вовсе
const pad = (value: number) => String(value).padStart(2, "0");

export const dayKey = (day: Date): string =>
  `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;

export const shiftDay = (key: string, days: number): string => {
  const day = new Date(`${key}T00:00:00`);
  day.setDate(day.getDate() + days);

  return dayKey(day);
};

const dayFormat = new Intl.DateTimeFormat("ru-RU", {
  weekday: "short",
  day: "numeric",
  month: "long",
});

export const dayTitle = (key: string): string => {
  const today = dayKey(new Date());

  if (key === today) {
    return "Сегодня";
  }

  if (key === shiftDay(today, 1)) {
    return "Завтра";
  }

  if (key === shiftDay(today, -1)) {
    return "Вчера";
  }

  const label = dayFormat.format(new Date(`${key}T00:00:00`));

  return label.charAt(0).toUpperCase() + label.slice(1);
};
