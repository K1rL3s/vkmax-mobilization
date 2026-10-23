export const visitFormConstraints = {
  minutesMin: 15,
  minutesMax: 240,
  windowsMax: 5,
};

const pad = (value: number) => String(value).padStart(2, "0");

const minuteOfDay = (time: string) => {
  const [hours, rest] = time.split(":");

  return Number(hours) * 60 + Number(rest);
};

const clock = (total: number) =>
  `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;

const dayKey = (day: Date) =>
  `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;

export const todayKey = () => dayKey(new Date());

export const tomorrowKey = () =>
  dayKey(new Date(Date.now() + 24 * 60 * 60 * 1000));

export const visitWindows = (draft: {
  date: string;
  timeFrom: string;
  timeTo: string;
  minutes: number;
}): string[] => {
  const starts: string[] = [];

  if (!draft.date || !(draft.minutes >= 1)) {
    return starts;
  }

  for (
    let start = minuteOfDay(draft.timeFrom);
    start + draft.minutes <= minuteOfDay(draft.timeTo);
    start += draft.minutes
  ) {
    starts.push(`${draft.date}T${clock(start)}:00`);
  }

  return starts;
};

export const windowLabel = (startsAt: string, minutes: number) => {
  const from = startsAt.slice(11, 16);

  return `${from}–${clock(minuteOfDay(from) + minutes)}`;
};
