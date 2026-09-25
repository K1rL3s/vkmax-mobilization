import type { components } from "../../schema/generated";

import { address, findHouse, orgOf } from "./houses";
import { residencyForHouse, user } from "./profile";
import { houseRequests } from "./requests";
import { windowsOn } from "./reception-hours";
import {
  DAY,
  at,
  days,
  isoDate,
  minuteOfDay,
  moment,
  startOfToday,
  weekdayAfter,
  weekdayOf,
} from "./time";

type Schemas = components["schemas"];

type MockAppointment = {
  id: number;
  created_at: string;
  user_id: number;
  user_name: string;
  house_id: number;
  flat_number: string | null;
  starts_at: string;
  status: Schemas["AppointmentStatus"];
  request_id: number | null;
};

const appointments: MockAppointment[] = [
  {
    id: 1,
    created_at: days(-1),
    user_id: 1,
    user_name: "Тестовый Житель",
    house_id: 1,
    flat_number: null,
    starts_at: at(weekdayAfter(1), 10, 30),
    status: "booked",
    request_id: houseRequests(1, null).find((item) => item.status !== "done")!
      .id,
  },
  {
    id: 2,
    created_at: days(-2),
    user_id: 1002,
    user_name: "Алсу Гимранова",
    house_id: 1,
    flat_number: "112",
    starts_at: at(startOfToday(), 9, 30),
    status: "booked",
    request_id: houseRequests(1, "in_progress")[0].id,
  },
  {
    id: 3,
    created_at: days(-3),
    user_id: 1003,
    user_name: "Пётр Данилов",
    house_id: 1,
    flat_number: "63",
    starts_at: at(startOfToday(), 11, 0),
    status: "cancelled",
    request_id: null,
  },
];

let nextId = 10;

const takenBySomeone = (day: Date, minute: number) =>
  (day.getUTCDate() * 7 + Math.floor(minute / 60) * 3 + (minute % 60)) % 5 < 2;

const bookedAt = (houseId: number, startsAt: string) =>
  appointments.filter(
    (item) =>
      item.house_id === houseId &&
      item.status === "booked" &&
      item.starts_at === startsAt,
  ).length;

export const receptionSlots = (
  houseId: number,
  onDate: string | undefined,
): Schemas["ReceptionSlotItem"][] => {
  const orgId = orgOf(houseId);
  const slots: Schemas["ReceptionSlotItem"][] = [];

  if (orgId === null) {
    return slots;
  }

  const now = Date.now();
  const today = startOfToday();

  for (let offset = 0; offset <= 14; offset += 1) {
    const day = new Date(today.getTime() + offset * DAY);

    if (onDate !== undefined && isoDate(day) !== onDate) {
      continue;
    }

    for (const window of windowsOn(orgId, weekdayOf(day))) {
      const to = minuteOfDay(window.time_to);

      for (
        let minute = minuteOfDay(window.time_from);
        minute + window.slot_minutes <= to;
        minute += window.slot_minutes
      ) {
        const startsAt = moment(day, minute).toISOString();

        if (new Date(startsAt).getTime() > now) {
          slots.push({
            starts_at: startsAt,
            is_free:
              bookedAt(houseId, startsAt) +
                (takenBySomeone(day, minute) ? 1 : 0) <
              window.capacity,
          });
        }
      }
    }
  }

  return slots.sort((a, b) => a.starts_at.localeCompare(b.starts_at));
};

const appointmentItem = (item: MockAppointment): Schemas["AppointmentItem"] => {
  const house = findHouse(item.house_id)!;
  const org = house.org!;

  return {
    id: item.id,
    created_at: item.created_at,
    org_id: org.id,
    house_id: house.id,
    address: address(house),
    starts_at: item.starts_at,
    status: item.status,
    org_address: org.address,
    org_phone: org.phone,
    request_id: item.request_id,
    user_name: item.user_name,
    flat_number:
      item.flat_number ??
      (item.user_id === user.user_id
        ? (residencyForHouse(item.house_id)?.flat_number ?? null)
        : null),
  };
};

const listAppointments = (items: MockAppointment[], order: 1 | -1) =>
  items
    .map(appointmentItem)
    .sort((a, b) => order * a.starts_at.localeCompare(b.starts_at));

export const myAppointments = (): Schemas["AppointmentItem"][] =>
  listAppointments(
    appointments.filter((item) => item.user_id === user.user_id),
    -1,
  );

export const orgAppointments = (
  orgId: number,
  onDate: string,
): Schemas["AppointmentItem"][] =>
  listAppointments(
    appointments.filter(
      (item) =>
        orgOf(item.house_id) === orgId &&
        isoDate(new Date(item.starts_at)) === onDate,
    ),
    1,
  );

export const findAppointment = (
  appointmentId: number,
): MockAppointment | undefined =>
  appointments.find((item) => item.id === appointmentId);

export const bookAppointment = (
  houseId: number,
  startsAt: string,
  requestId: number | null,
): Schemas["AppointmentItem"] => {
  const created: MockAppointment = {
    id: nextId++,
    created_at: new Date().toISOString(),
    user_id: user.user_id,
    user_name: user.name,
    house_id: houseId,
    flat_number: residencyForHouse(houseId)?.flat_number ?? null,
    starts_at: startsAt,
    status: "booked",
    request_id: requestId,
  };
  appointments.push(created);

  return appointmentItem(created);
};
