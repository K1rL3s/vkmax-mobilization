import type { components } from "@/shared/api/schema/generated";

export type ReceptionSlot = components["schemas"]["ReceptionSlotItem"];

export type Appointment = components["schemas"]["AppointmentItem"];

export type AccessRequest = components["schemas"]["AccessRequestItem"];

// календарный день приёма: полночь UTC этой даты, а не момент времени. Его
// подписи считаются в UTC, поэтому не зависят ни от пояса телефона, ни от
// пояса УК
export type ReceptionDay = {
  key: string;
  date: Date;
  slots: ReceptionSlot[];
};

export type Schedule = ReturnType<typeof createSchedule>;

// перерыв длиннее этого - уже не обед, а, например, вечерний приём: такой
// разрыв делит слоты, но подписью «обед» не называется
const MAX_LUNCH_MINUTES = 120;

const MINUTE = 60 * 1000;

const calendarKeyFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: "UTC",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

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

export const dateLabel = (day: Date) => dateFormat.format(day);

export const dayTitle = (day: Date) =>
  `${weekdayLabel(day)}, ${dateLabel(day)}`;

// сегодняшний день пуст и тогда, когда приём уже закончился, поэтому в
// подпись о выходных он не попадает. Дни недели идут с понедельника, с какого
// бы дня ни начиналась лента
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

// всё, что зависит от момента времени, считается в поясе УК: житель в другом
// городе видит часы приёма такими, какими их видит офис
export const createSchedule = (timeZone: string) => {
  const keyFormat = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  // «9:00», а не «09:00»: в сетке из четырёх слотов на узком экране ведущий
  // ноль не помещается в кнопку
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

    // лента дней идёт подряд от сегодня до последнего дня со слотами: дни без
    // приёма остаются в ней неактивными, чтобы житель видел, что это выходной,
    // а не пропуск в календаре
    receptionDays: (
      slots: ReceptionSlot[],
      now = new Date(),
    ): ReceptionDay[] => {
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
        let date = calendarDay(dayKey(now));
        calendarKeyFormat.format(date) <= lastKey;
        date = new Date(date.getTime() + 24 * 60 * MINUTE)
      ) {
        const key = calendarKeyFormat.format(date);
        days.push({ key, date, slots: byDay.get(key) ?? [] });
      }

      return days;
    },

    // обед виден в самих данных: занятые слоты бэк тоже присылает, поэтому
    // разрыв шире обычного шага между соседями - это перерыв в окнах приёма
    splitDay: (slots: ReceptionSlot[]) => {
      const times = slots.map((slot) => Date.parse(slot.starts_at));
      const steps = times.slice(1).map((time, index) => time - times[index]);
      const step = Math.min(...steps);
      const gapAt = steps.findIndex((gap) => gap > step);

      if (gapAt === -1) {
        return { morning: slots, afternoon: [], lunch: null };
      }

      const lunchFrom = new Date(times[gapAt] + step).toISOString();
      const lunchTo = slots[gapAt + 1].starts_at;

      return {
        morning: slots.slice(0, gapAt + 1),
        afternoon: slots.slice(gapAt + 1),
        lunch:
          steps[gapAt] - step <= MAX_LUNCH_MINUTES * MINUTE
            ? `обед ${slotTime(lunchFrom)}-${slotTime(lunchTo)}`
            : null,
      };
    },
  };
};

// у дома без УК пояса нет: подписи тогда в поясе телефона
export const deviceTimeZone = () =>
  Intl.DateTimeFormat().resolvedOptions().timeZone;
