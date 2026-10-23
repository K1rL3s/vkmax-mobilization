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

export const pickVisitWindow = (requestId: number, slotId: number) => {
  const visit = visits.get(requestId);

  if (!visit?.windows.some((window) => window.id === slotId)) {
    return "Окно визита не найдено";
  }

  visit.slot_id = slotId;
  return null;
};

export const declineVisit = (requestId: number, visitId: number) => {
  const visit = visits.get(requestId);

  if (visit?.id !== visitId) {
    return "Визит не найден";
  }

  visit.slot_id = null;
  return null;
};
