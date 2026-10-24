import type { components } from "../../schema/generated";

type Visit = components["schemas"]["VisitItem"];

let nextVisitId = 7001;
let nextWindowId = 9001;

export const makeVisit = (
  date: string,
  starts: string[],
  minutes: number,
): Visit => ({
  id: nextVisitId++,
  date,
  windows: starts.map((start) => ({
    id: nextWindowId++,
    starts_at: new Date(start).toISOString(),
    minutes,
  })),
  slot_id: null,
});

const tomorrow = () => {
  const day = new Date(Date.now() + 24 * 60 * 60 * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");

  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;
};

const visits = new Map<number, Visit>([
  [
    139,
    makeVisit(
      tomorrow(),
      [10, 12, 14].map((hour) => `${tomorrow()}T${hour}:00:00`),
      120,
    ),
  ],
]);

export const visitOf = (requestId: number): Visit | null =>
  visits.get(requestId) ?? null;

type VisitWindow = Visit["windows"][number];

type VisitRefusal = { kind: "missing" | "refused"; message: string };

const UNDER_WAY = "Визит уже начался: поменять время нельзя";

const timeFormat = new Intl.DateTimeFormat("ru-RU", {
  hour: "2-digit",
  minute: "2-digit",
});

const dayFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
});

const hasStarted = (window: VisitWindow) =>
  Date.parse(window.starts_at) <= Date.now();

const pickedOf = (visit: Visit) =>
  visit.windows.find((window) => window.id === visit.slot_id);

const span = (window: VisitWindow) => {
  const starts = Date.parse(window.starts_at);

  return `${timeFormat.format(starts)}–${timeFormat.format(starts + window.minutes * 60_000)}`;
};

const chosenNote = (window: VisitWindow, was: VisitWindow | undefined) => {
  const when = `${dayFormat.format(Date.parse(window.starts_at)).replace(".", "")}, ${span(window)}`;

  if (!was) return `Удобное время визита: ${when}`;

  return `Удобнее другое время визита: ${when} вместо ${span(was)}`;
};

export const pickVisitWindow = (
  requestId: number,
  slotId: number,
): VisitRefusal | { kind: "kept" } | { kind: "picked"; note: string } => {
  const visit = visits.get(requestId);
  const window = visit?.windows.find((item) => item.id === slotId);

  if (!visit || !window) {
    return { kind: "missing", message: "Окно визита не найдено" };
  }

  if (visit.slot_id === slotId) return { kind: "kept" };

  const was = pickedOf(visit);

  if (was && hasStarted(was)) return { kind: "refused", message: UNDER_WAY };

  if (hasStarted(window)) {
    return { kind: "refused", message: "Окно визита уже началось или прошло" };
  }

  visit.slot_id = slotId;
  return { kind: "picked", note: chosenNote(window, was) };
};

export const declineVisit = (
  requestId: number,
  visitId: number,
): VisitRefusal | null => {
  const visit = visits.get(requestId);

  if (visit?.id !== visitId) {
    return { kind: "missing", message: "Визит не найден" };
  }

  const picked = pickedOf(visit);

  if (picked && hasStarted(picked)) {
    return { kind: "refused", message: UNDER_WAY };
  }

  visit.slot_id = null;
  return null;
};
