export const pad = (value: number) => String(value).padStart(2, "0");

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

export const minuteOfDay = (time: string) => {
  const [hours, rest] = time.split(":");

  return Number(hours) * 60 + Number(rest);
};

export const clock = (total: number) =>
  `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;

export const slotLabels = (
  spans: [string, string][],
  minutes: number,
): string[] =>
  minutes < 1
    ? []
    : spans.flatMap(([from, to]) => {
        const labels: string[] = [];

        for (
          let start = minuteOfDay(from);
          start + minutes <= minuteOfDay(to);
          start += minutes
        ) {
          labels.push(`${clock(start)}-${clock(start + minutes)}`);
        }

        return labels;
      });
