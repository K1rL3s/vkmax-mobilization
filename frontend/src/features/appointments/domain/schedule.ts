import type { components } from "@/shared/api/schema/generated";
import type { StatusPillTone } from "@/shared/ui/status-pill";

export type ReceptionSlot = components["schemas"]["ReceptionSlotItem"];

export type Appointment = components["schemas"]["AppointmentItem"];

export type AccessRequest = components["schemas"]["AccessRequestItem"];

export type ReceptionDay = {
  key: string;
  date: Date;
  slots: ReceptionSlot[];
};

export type Schedule = ReturnType<typeof createSchedule>;

const MINUTE = 60 * 1000;

const weekdayFormat = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "UTC",
  weekday: "short",
});

const monthFormat = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "UTC",
  month: "long",
});

const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "UTC",
  day: "numeric",
  month: "long",
});

const capitalize = (text: string) =>
  text.charAt(0).toUpperCase() + text.slice(1);

export const calendarDay = (key: string) => new Date(`${key}T00:00:00Z`);

export const weekdayLabel = (day: Date) =>
  capitalize(weekdayFormat.format(day));

export const monthLabel = (day: Date) => capitalize(monthFormat.format(day));

const dateLabel = (day: Date) => dateFormat.format(day);

export const dayTitle = (day: Date) =>
  `${weekdayLabel(day)}, ${dateLabel(day)}`;

export const closedDaysCaption = (days: ReceptionDay[]) => {
  const closed = new Map(
    days
      .slice(1)
      .filter((day) => day.slots.length === 0)
      .map((day) => [(day.date.getUTCDay() + 6) % 7, weekdayLabel(day.date)]),
  );
  const names = [...closed.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, name]) => name);

  if (names.length === 0) {
    return null;
  }

  const listed =
    names.length === 1
      ? names[0]
      : `${names.slice(0, -1).join(", ")} и ${names.at(-1)}`;

  return `${listed}: приёма нет`;
};

export const createSchedule = (timeZone: string) => {
  const keyFormat = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const timeFormat = new Intl.DateTimeFormat("ru-RU", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
  });

  const dayKey = (moment: Date | string) => keyFormat.format(new Date(moment));
  const slotTime = (iso: string) => timeFormat.format(new Date(iso));
  const dayOf = (iso: string) => calendarDay(dayKey(iso));

  return {
    dayKey,
    slotTime,
    slotDate: (iso: string) => dateLabel(dayOf(iso)),
    appointmentTitle: (iso: string) =>
      `${dayTitle(dayOf(iso))}, ${slotTime(iso)}`,

    receptionDays: (slots: ReceptionSlot[]): ReceptionDay[] => {
      const last = slots.at(-1);

      if (!last) {
        return [];
      }

      const byDay = new Map<string, ReceptionSlot[]>();

      for (const slot of slots) {
        const key = dayKey(slot.starts_at);
        byDay.set(key, [...(byDay.get(key) ?? []), slot]);
      }

      const lastKey = dayKey(last.starts_at);
      const days: ReceptionDay[] = [];

      for (
        let date = calendarDay(dayKey(new Date()));
        date.toISOString().slice(0, 10) <= lastKey;
        date = new Date(date.getTime() + 24 * 60 * MINUTE)
      ) {
        const key = date.toISOString().slice(0, 10);
        days.push({ key, date, slots: byDay.get(key) ?? [] });
      }

      return days;
    },

    splitDay: (slots: ReceptionSlot[]) => {
      const times = slots.map((slot) => Date.parse(slot.starts_at));
      const steps = times.slice(1).map((time, index) => time - times[index]);
      const step = Math.min(...steps);
      const gapAt = steps.findIndex((gap) => gap > step);

      if (gapAt === -1) {
        return { groups: [{ title: null, slots }], lunch: null };
      }

      const lunchFrom = new Date(times[gapAt] + step).toISOString();
      const lunchTo = slots[gapAt + 1].starts_at;

      return {
        groups: [
          { title: "До обеда", slots: slots.slice(0, gapAt + 1) },
          { title: "После обеда", slots: slots.slice(gapAt + 1) },
        ],
        lunch:
          steps[gapAt] - step <= 120 * MINUTE
            ? `обед ${slotTime(lunchFrom)}-${slotTime(lunchTo)}`
            : null,
      };
    },
  };
};

export const deviceTimeZone = () =>
  Intl.DateTimeFormat().resolvedOptions().timeZone;

export const appointmentSubject = (appointment: Appointment) =>
  appointment.request_id
    ? `Обсудить заявку №${appointment.request_id} · офис УК`
    : "Общий вопрос · офис УК";

export type AppointmentState = "upcoming" | "passed" | "cancelled" | "done";

export const appointmentState = (
  appointment: Appointment,
): AppointmentState => {
  if (appointment.status !== "booked") {
    return appointment.status;
  }

  return Date.parse(appointment.starts_at) > Date.now() ? "upcoming" : "passed";
};

export const appointmentLabel = (state: AppointmentState): string =>
  ({
    upcoming: "Запись активна",
    passed: "Приём прошёл",
    cancelled: "Запись отменена",
    done: "Приём состоялся",
  })[state];

export const appointmentTone = (state: AppointmentState): StatusPillTone =>
  (
    ({
      upcoming: "themed",
      passed: "neutral",
      cancelled: "negative",
      done: "positive",
    }) satisfies Record<AppointmentState, StatusPillTone>
  )[state];
