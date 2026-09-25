import type { components } from "@/shared/api/schema/generated";

export type ReceptionWindow = components["schemas"]["ReceptionWindowItem"];

export type Appointment = components["schemas"]["AppointmentItem"];

export type ReceptionWindowInput =
  components["schemas"]["ReceptionWindowInput"];

// день недели нумеруется с понедельника, как в контракте. `at` - готовая
// форма для подписи «Принимаем во вторник»: склонять на лету нечем
export const WEEKDAYS = [
  { value: 0, short: "Пн", at: "в понедельник" },
  { value: 1, short: "Вт", at: "во вторник" },
  { value: 2, short: "Ср", at: "в среду" },
  { value: 3, short: "Чт", at: "в четверг" },
  { value: 4, short: "Пт", at: "в пятницу" },
  { value: 5, short: "Сб", at: "в субботу" },
  { value: 6, short: "Вс", at: "в воскресенье" },
];

// границы повторяют ReceptionService.set_windows бэка, длина перерыва - наша:
// окно короче слота не вместит ни одной записи
export const receptionFormConstraints = {
  slotMin: 5,
  slotMax: 240,
  capacityMin: 1,
  capacityMax: 20,
};

// бэк отдаёт время как HH:MM:SS, поле ввода принимает и возвращает HH:MM
export const asTime = (value: string): string => value.slice(0, 5);

// в подписи час без ведущего нуля: «9:00», а не «09:00»
const spoken = (value: string) => asTime(value).replace(/^0/, "");

const minutes = (time: string) => {
  const [hours, rest] = asTime(time).split(":");

  return Number(hours) * 60 + Number(rest);
};

const byStart = (a: ReceptionWindow, b: ReceptionWindow) =>
  minutes(a.time_from) - minutes(b.time_from);

export const windowsOfDay = (
  windows: ReceptionWindow[],
  weekday: number,
): ReceptionWindow[] =>
  windows.filter((window) => window.weekday === weekday).sort(byStart);

// день описывается одной строкой: два окна - это обед, разрыв между ними
const dayHours = (day: ReceptionWindow[]) => {
  const first = day[0];
  const last = day[day.length - 1];

  if (!first || !last) {
    return null;
  }

  const span = `${spoken(first.time_from)}-${spoken(last.time_to)}`;

  return day.length > 1
    ? `${span}, перерыв ${spoken(first.time_to)}-${spoken(last.time_from)}`
    : span;
};

export const dayLabel = (
  windows: ReceptionWindow[],
  weekday: number,
): string | null => dayHours(windowsOfDay(windows, weekday));

// подряд идущие дни с одинаковыми часами сливаются в «Пн-Пт»: расписание УК
// обычно одинаково всю неделю, и перечисление по дню не помещается в строку
const runsOfDays = (windows: ReceptionWindow[]) => {
  const runs: { from: number; to: number; hours: string }[] = [];

  for (const weekday of WEEKDAYS) {
    const hours = dayLabel(windows, weekday.value);

    if (hours === null) {
      continue;
    }

    const last = runs[runs.length - 1];

    if (last && last.hours === hours && last.to === weekday.value - 1) {
      last.to = weekday.value;
    } else {
      runs.push({ from: weekday.value, to: weekday.value, hours });
    }
  }

  return runs;
};

// сводка перечисляет дни приёма и заканчивается длиной слота, когда она у всех
// дней одна: разные длины в одну строку не помещаются и уводят в редактор
export const scheduleSummary = (windows: ReceptionWindow[]): string => {
  const days = runsOfDays(windows).map((run) => {
    const from = WEEKDAYS[run.from]?.short;
    const to = WEEKDAYS[run.to]?.short;

    return `${run.to > run.from ? `${from}-${to}` : from} ${run.hours}`;
  });

  if (days.length === 0) {
    return "Приём не ведётся";
  }

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

export const emptyDay: DayDraft = {
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
  const last = day[day.length - 1];

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
): ReceptionWindowInput[] => {
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

// `PUT` заменяет сетку целиком, поэтому правка одного дня отправляется вместе
// со всеми известными окнами остальных дней
export const gridWithDay = (
  windows: ReceptionWindow[],
  weekday: number,
  draft: DayDraft,
): ReceptionWindowInput[] => [
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

// сколько записей поместится в день: то, ради чего и правят длину слота
export const slotsPerDay = (draft: DayDraft): number => {
  if (!draft.enabled || draft.slotMinutes < 1) {
    return 0;
  }

  const spans = draft.hasBreak
    ? [
        [draft.timeFrom, draft.breakFrom],
        [draft.breakTo, draft.timeTo],
      ]
    : [[draft.timeFrom, draft.timeTo]];

  return spans.reduce((total, [from, to]) => {
    const span = minutes(to ?? "") - minutes(from ?? "");

    return total + Math.max(0, Math.floor(span / draft.slotMinutes));
  }, 0);
};

export const dayError = (draft: DayDraft): string | null => {
  if (!draft.enabled) {
    return null;
  }

  if (minutes(draft.timeFrom) >= minutes(draft.timeTo)) {
    return "Приём кончается раньше, чем начинается";
  }

  if (!draft.hasBreak) {
    return null;
  }

  if (minutes(draft.breakFrom) >= minutes(draft.breakTo)) {
    return "Перерыв кончается раньше, чем начинается";
  }

  return minutes(draft.breakFrom) < minutes(draft.timeFrom) ||
    minutes(draft.breakTo) > minutes(draft.timeTo)
    ? "Перерыв не помещается в часы приёма"
    : null;
};
