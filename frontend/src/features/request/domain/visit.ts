import { formatTime } from "@/shared/lib/format";

import type { RequestCard } from "./types";

export type Visit = NonNullable<RequestCard["visit"]>;

type VisitWindow = Visit["windows"][number];

const visitDayFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
});

export const visitDay = (date: string) =>
  visitDayFormat.format(new Date(`${date}T00:00:00`)).replace(".", "");

export const windowSpan = (window: VisitWindow) => {
  const ends = Date.parse(window.starts_at) + window.minutes * 60 * 1000;

  return `${formatTime(window.starts_at)}–${formatTime(new Date(ends).toISOString())}`;
};

export const pickedWindow = (visit: Visit) =>
  visit.windows.find((window) => window.id === visit.slot_id);

export const hasStarted = (window: VisitWindow, now: number) =>
  Date.parse(window.starts_at) <= now;

export const visitLine = (visit: Visit) => {
  const picked = pickedWindow(visit);

  return picked ? `${visitDay(visit.date)}, ${windowSpan(picked)}` : null;
};
