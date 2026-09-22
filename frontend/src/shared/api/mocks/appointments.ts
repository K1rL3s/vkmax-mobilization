import type { components } from "../schema/generated";

import { conflict, forbidden, notFound, number, ok, route } from "./reply";
import {
  address,
  findHouse,
  houseRequests,
  residencies,
  residencyForHouse,
  type MockHttpRequest,
} from "./state";

type Schemas = components["schemas"];

const DAY = 24 * 60 * 60 * 1000;

// бэк отдаёт слоты на две недели вперёд от сегодняшнего дня
const HORIZON_DAYS = 14;

// окна приёма настроены только у первой УК: дом второй показывает экран без
// приёма. Пн-пт, два окна по 30 минут, один житель на слот
const RECEPTION_ORG_ID = 1;

const WINDOWS = [
  { from: 9 * 60, to: 13 * 60 },
  { from: 14 * 60, to: 18 * 60 },
];

const SLOT_MINUTES = 30;

type MockAppointment = {
  id: number;
  created_at: string;
  house_id: number;
  starts_at: string;
  status: Schemas["AppointmentStatus"];
  request_id: number | null;
};

type MockAccessRequest = {
  id: number;
  created_at: string;
  house_id: number;
  reason: string;
  date: string;
  slots: Schemas["AccessSlotItem"][];
  responded_count: number;
  targets_count: number;
  my_slot_id: number | null;
};

const houseOf = (request: MockHttpRequest): number | null =>
  number(request.headers["x-house-id"]) ??
  residencies().at(-1)?.house_id ??
  null;

// часы приёма заданы в поясе УК (у мок-организаций это Москва, UTC+3 без
// перехода на летнее время), а не в поясе машины, где запущен мок. День здесь -
// полночь UTC московской даты, момент - сдвиг от неё
const ORG_OFFSET_MINUTES = 3 * 60;

const MINUTE = 60 * 1000;

const startOfToday = () => {
  const today = new Date(Date.now() + ORG_OFFSET_MINUTES * MINUTE);
  today.setUTCHours(0, 0, 0, 0);

  return today;
};

const isoDate = (day: Date) => day.toISOString().slice(0, 10);

const isWeekend = (day: Date) => day.getUTCDay() === 0 || day.getUTCDay() === 6;

const moment = (day: Date, minute: number) =>
  new Date(day.getTime() + (minute - ORG_OFFSET_MINUTES) * MINUTE);

// ближайший будний день не раньше чем через `offset` дней
const weekdayAfter = (offset: number) => {
  const day = new Date(startOfToday().getTime() + offset * DAY);

  while (isWeekend(day)) {
    day.setUTCDate(day.getUTCDate() + 1);
  }

  return day;
};

const at = (day: Date, hours: number, minutes = 0) =>
  moment(day, hours * 60 + minutes).toISOString();

const firstDay = weekdayAfter(1);

const appointments: MockAppointment[] = [
  {
    id: 1,
    created_at: new Date(Date.now() - DAY).toISOString(),
    house_id: 1,
    starts_at: at(firstDay, 10, 30),
    status: "booked",
    request_id:
      houseRequests(1, null).find((item) => item.status !== "done")?.id ?? null,
  },
];

const accessDay = weekdayAfter(3);

const accessRequests: MockAccessRequest[] = [
  {
    id: 1,
    created_at: new Date(Date.now() - DAY).toISOString(),
    house_id: 1,
    reason:
      "Плановая проверка газового оборудования: мастер осмотрит плиту и подводку, займёт 15 минут",
    date: isoDate(accessDay),
    slots: [
      { id: 11, starts_at: at(accessDay, 9), capacity: 6, taken: 2 },
      { id: 12, starts_at: at(accessDay, 12), capacity: 6, taken: 6 },
      { id: 13, starts_at: at(accessDay, 15), capacity: 6, taken: 1 },
      { id: 14, starts_at: at(accessDay, 18), capacity: 6, taken: 0 },
    ],
    responded_count: 9,
    targets_count: 40,
    my_slot_id: null,
  },
];

// часть слотов занята соседями: номер получаса решает детерминированно, чтобы
// картина не прыгала между запросами
const takenBySomeone = (day: Date, minute: number) =>
  (day.getUTCDate() * 7 + Math.floor(minute / 60) * 3 + (minute % 60)) % 5 < 2;

const isBooked = (startsAt: string) =>
  appointments.some(
    (item) => item.status === "booked" && item.starts_at === startsAt,
  );

const receptionSlots = (onDate: string | undefined) => {
  const now = Date.now();
  const today = startOfToday();
  const slots: Schemas["ReceptionSlotItem"][] = [];

  for (let offset = 0; offset <= HORIZON_DAYS; offset += 1) {
    const day = new Date(today.getTime() + offset * DAY);

    if (isWeekend(day)) {
      continue;
    }

    if (onDate !== undefined && isoDate(day) !== onDate) {
      continue;
    }

    for (const window of WINDOWS) {
      for (
        let minute = window.from;
        minute < window.to;
        minute += SLOT_MINUTES
      ) {
        const startsAt = moment(day, minute);

        if (startsAt.getTime() <= now) {
          continue;
        }

        slots.push({
          starts_at: startsAt.toISOString(),
          is_free:
            !takenBySomeone(day, minute) && !isBooked(startsAt.toISOString()),
        });
      }
    }
  }

  return slots;
};

const hasReception = (houseId: number) =>
  findHouse(houseId)?.org?.id === RECEPTION_ORG_ID;

const appointmentItem = (
  item: MockAppointment,
): Schemas["AppointmentItem"] | null => {
  const house = findHouse(item.house_id);

  if (!house?.org) {
    return null;
  }

  return {
    id: item.id,
    created_at: item.created_at,
    org_id: house.org.id,
    house_id: house.id,
    address: address(house),
    starts_at: item.starts_at,
    status: item.status,
    org_address: house.org.address,
    org_phone: house.org.phone,
    request_id: item.request_id,
  };
};

const accessRequestItem = (
  item: MockAccessRequest,
): Schemas["AccessRequestItem"] => {
  const house = findHouse(item.house_id);

  return {
    id: item.id,
    created_at: item.created_at,
    house_id: item.house_id,
    address: house ? address(house) : "",
    reason: item.reason,
    date: item.date,
    slots: item.slots,
    responded_count: item.responded_count,
    targets_count: item.targets_count,
    my_flat_id: residencyForHouse(item.house_id)?.flat_id ?? null,
    my_slot_id: item.my_slot_id,
  };
};

export const appointmentsConfigs = [
  {
    path: "/houses/:house_id/reception-slots" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const houseId = Number(request.params.house_id);

        if (!findHouse(houseId)) {
          return notFound("Дом не найден");
        }

        if (!residencyForHouse(houseId)) {
          return forbidden("Вы не живёте в этом доме");
        }

        return ok(
          hasReception(houseId) ? receptionSlots(request.query.on_date) : [],
        );
      }),
    ],
  },
  {
    path: "/appointments" as const,
    method: "get" as const,
    routes: [
      route(() =>
        ok(
          appointments
            .map(appointmentItem)
            .filter((item) => item !== null)
            // бэк отдаёт записи от поздних к ранним
            .sort((a, b) => b.starts_at.localeCompare(a.starts_at)),
        ),
      ),
    ],
  },
  {
    path: "/appointments" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const houseId = houseOf(request);

        if (houseId === null) {
          return forbidden("Укажите X-House-Id");
        }

        const body = request.body as Schemas["BookAppointmentRequest"];
        const startsAt = new Date(body.starts_at).toISOString();
        const slot = hasReception(houseId)
          ? receptionSlots(undefined).find(
              (item) => item.starts_at === startsAt,
            )
          : undefined;

        if (!slot) {
          return conflict("Такого слота приема нет");
        }

        if (!slot.is_free) {
          return conflict("Слот уже занят");
        }

        const requestId = body.request_id ?? null;

        if (
          requestId !== null &&
          !houseRequests(houseId, null).some((item) => item.id === requestId)
        ) {
          return notFound("Заявка не найдена");
        }

        const created: MockAppointment = {
          id: Math.max(0, ...appointments.map((item) => item.id)) + 1,
          created_at: new Date().toISOString(),
          house_id: houseId,
          starts_at: startsAt,
          status: "booked",
          request_id: requestId,
        };
        appointments.push(created);

        return ok(appointmentItem(created));
      }),
    ],
  },
  {
    path: "/appointments/:appointment_id" as const,
    method: "delete" as const,
    routes: [
      route((request) => {
        const found = appointments.find(
          (item) => item.id === Number(request.params.appointment_id),
        );

        if (!found) {
          return notFound("Запись не найдена");
        }

        if (found.status === "done") {
          return conflict("Прием уже прошел");
        }

        found.status = "cancelled";

        return ok({ ok: true } satisfies Schemas["OkResponse"]);
      }),
    ],
  },
  {
    path: "/access-requests" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const houseId = houseOf(request);

        // бэк ищет запросы по квартире жителя, а мок заводит квартиру только
        // после подтверждения: без этого послабления экран доступа не открыть
        return ok(
          houseId !== null && residencyForHouse(houseId)
            ? accessRequests
                .filter((item) => item.house_id === houseId)
                .map(accessRequestItem)
            : [],
        );
      }),
    ],
  },
  {
    path: "/access-requests/:access_request_id/slots/:slot_id" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const found = accessRequests.find(
          (item) => item.id === Number(request.params.access_request_id),
        );

        // выбирать окно может только подтверждённый житель, остальным бэк
        // отвечает, будто запроса нет
        if (!found || !residencyForHouse(found.house_id)?.verified) {
          return notFound("Запрос доступа не найден");
        }

        const slot = found.slots.find(
          (item) => item.id === Number(request.params.slot_id),
        );

        if (!slot) {
          return notFound("Слот не найден");
        }

        if (found.my_slot_id !== slot.id) {
          if (slot.taken >= slot.capacity) {
            return conflict("В этом окне мест больше нет");
          }

          const previous = found.slots.find(
            (item) => item.id === found.my_slot_id,
          );

          if (previous) {
            previous.taken -= 1;
          } else {
            found.responded_count += 1;
          }

          slot.taken += 1;
          found.my_slot_id = slot.id;
        }

        return ok(accessRequestItem(found));
      }),
    ],
  },
];
