import type { components } from "@/shared/api/schema/generated";

import { minuteOfDay, slotLabels } from "./day";

export type ReceptionWindow = components["schemas"]["ReceptionWindowItem"];

export type Appointment = components["schemas"]["AppointmentItem"];

export const WEEKDAYS = [
  { value: 0, short: "Пн", at: "в понедельник" },
  { value: 1, short: "Вт", at: "во вторник" },
  { value: 2, short: "Ср", at: "в среду" },
  { value: 3, short: "Чт", at: "в четверг" },
  { value: 4, short: "Пт", at: "в пятницу" },
  { value: 5, short: "Сб", at: "в субботу" },
  { value: 6, short: "Вс", at: "в воскресенье" },
];

export const receptionFormConstraints = {
  slotMin: 5,
  slotMax: 240,
  capacityMin: 1,
  capacityMax: 20,
};

const asTime = (value: string): string => value.slice(0, 5);

const spoken = (value: string) => asTime(value).replace(/^0/, "");

const byStart = (a: ReceptionWindow, b: ReceptionWindow) =>
  minuteOfDay(a.time_from) - minuteOfDay(b.time_from);

const windowsOfDay = (
  windows: ReceptionWindow[],
  weekday: number,
): ReceptionWindow[] =>
  windows.filter((window) => window.weekday === weekday).sort(byStart);

export const dayLabel = (
  windows: ReceptionWindow[],
  weekday: number,
): string | null => {
  const day = windowsOfDay(windows, weekday);
  const first = day[0];
  const last = day.at(-1);

  if (!first || !last) {
    return null;
  }

  const span = `${spoken(first.time_from)}-${spoken(last.time_to)}`;

  return day.length > 1
    ? `${span}, перерыв ${spoken(first.time_to)}-${spoken(last.time_from)}`
    : span;
};

export const scheduleSummary = (windows: ReceptionWindow[]): string => {
  const runs: {
    from: (typeof WEEKDAYS)[number];
    to: (typeof WEEKDAYS)[number];
    hours: string;
  }[] = [];

  for (const weekday of WEEKDAYS) {
    const hours = dayLabel(windows, weekday.value);
    const last = runs.at(-1);

    if (hours === null) {
      continue;
    }

    if (last && last.hours === hours && last.to.value === weekday.value - 1) {
      last.to = weekday;
    } else {
      runs.push({ from: weekday, to: weekday, hours });
    }
  }

  if (runs.length === 0) {
    return "Приём не ведётся";
  }

  const days = runs.map(
    (run) =>
      `${run.to === run.from ? run.from.short : `${run.from.short}-${run.to.short}`} ${run.hours}`,
  );
  const lengths = new Set(windows.map((window) => window.slot_minutes));
  const slot = lengths.size === 1 ? `, по ${[...lengths][0]} минут` : "";

  return `${days.join(", ")}${slot}`;
};

export type DayDraft = {
  enabled: boolean;
  timeFrom: string;
  timeTo: string;
  hasBreak: boolean;
  breakFrom: string;
  breakTo: string;
  slotMinutes: number;
  capacity: number;
};

const emptyDay: DayDraft = {
  enabled: false,
  timeFrom: "09:00",
  timeTo: "18:00",
  hasBreak: false,
  breakFrom: "13:00",
  breakTo: "14:00",
  slotMinutes: 30,
  capacity: 1,
};

export const draftOfDay = (
  windows: ReceptionWindow[],
  weekday: number,
): DayDraft => {
  const day = windowsOfDay(windows, weekday);
  const first = day[0];
  const last = day.at(-1);

  if (!first || !last) {
    return emptyDay;
  }

  return {
    enabled: true,
    timeFrom: asTime(first.time_from),
    timeTo: asTime(last.time_to),
    hasBreak: day.length > 1,
    breakFrom: day.length > 1 ? asTime(first.time_to) : emptyDay.breakFrom,
    breakTo: day.length > 1 ? asTime(last.time_from) : emptyDay.breakTo,
    slotMinutes: first.slot_minutes,
    capacity: first.capacity,
  };
};

const windowsOfDraft = (
  draft: DayDraft,
  weekday: number,
): components["schemas"]["ReceptionWindowInput"][] => {
  if (!draft.enabled) {
    return [];
  }

  const shared = {
    weekday,
    slot_minutes: draft.slotMinutes,
    capacity: draft.capacity,
  };

  return draft.hasBreak
    ? [
        { ...shared, time_from: draft.timeFrom, time_to: draft.breakFrom },
        { ...shared, time_from: draft.breakTo, time_to: draft.timeTo },
      ]
    : [{ ...shared, time_from: draft.timeFrom, time_to: draft.timeTo }];
};

export const gridWithDay = (
  windows: ReceptionWindow[],
  weekday: number,
  draft: DayDraft,
): components["schemas"]["ReceptionWindowInput"][] => [
  ...windows
    .filter((window) => window.weekday !== weekday)
    .sort((a, b) => a.weekday - b.weekday || byStart(a, b))
    .map((window) => ({
      weekday: window.weekday,
      time_from: asTime(window.time_from),
      time_to: asTime(window.time_to),
      slot_minutes: window.slot_minutes,
      capacity: window.capacity,
    })),
  ...windowsOfDraft(draft, weekday),
];

export const daySlots = (draft: DayDraft): string[] =>
  draft.enabled
    ? slotLabels(
        draft.hasBreak
          ? [
              [draft.timeFrom, draft.breakFrom],
              [draft.breakTo, draft.timeTo],
            ]
          : [[draft.timeFrom, draft.timeTo]],
        draft.slotMinutes,
      )
    : [];

export const dayError = (draft: DayDraft): string | null => {
  if (!draft.enabled) {
    return null;
  }

  if (minuteOfDay(draft.timeFrom) >= minuteOfDay(draft.timeTo)) {
    return "Приём кончается раньше, чем начинается";
  }

  if (!draft.hasBreak) {
    return null;
  }

  if (minuteOfDay(draft.breakFrom) >= minuteOfDay(draft.breakTo)) {
    return "Перерыв кончается раньше, чем начинается";
  }

  return minuteOfDay(draft.breakFrom) < minuteOfDay(draft.timeFrom) ||
    minuteOfDay(draft.breakTo) > minuteOfDay(draft.timeTo)
    ? "Перерыв не помещается в часы приёма"
    : null;
};
