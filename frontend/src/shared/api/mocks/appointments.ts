import type { components } from "../schema/generated";

import { conflict, forbidden, notFound, number, ok, route } from "./reply";
import {
  bookAppointment,
  cancelAppointment,
  chooseAccessSlot,
  findAccessRequest,
  findAppointment,
  findHouse,
  houseAccessRequests,
  houseRequests,
  myAppointments,
  receptionSlots,
  residencies,
  residencyForHouse,
  accessRequestItem,
  type MockHttpRequest,
} from "./state";

type Schemas = components["schemas"];

const houseOf = (request: MockHttpRequest): number | null =>
  number(request.headers["x-house-id"]) ??
  residencies().at(-1)?.house_id ??
  null;

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

        return ok(receptionSlots(houseId, request.query.on_date));
      }),
    ],
  },
  {
    path: "/appointments" as const,
    method: "get" as const,
    routes: [route(() => ok(myAppointments()))],
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
        const slot = receptionSlots(houseId, undefined).find(
          (item) => item.starts_at === startsAt,
        );

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

        return ok(bookAppointment(houseId, startsAt, requestId));
      }),
    ],
  },
  {
    path: "/appointments/:appointment_id" as const,
    method: "delete" as const,
    routes: [
      route((request) => {
        const found = findAppointment(Number(request.params.appointment_id));

        if (!found) {
          return notFound("Запись не найдена");
        }

        if (found.status === "done") {
          return conflict("Прием уже прошел");
        }

        cancelAppointment(found);

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
            ? houseAccessRequests(houseId)
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
        const found = findAccessRequest(
          Number(request.params.access_request_id),
        );

        // выбирать окно может только подтверждённый житель, остальным бэк
        // отвечает, будто запроса нет
        if (!found || !residencyForHouse(found.house_id)?.verified) {
          return notFound("Запрос доступа не найден");
        }

        const outcome = chooseAccessSlot(found, Number(request.params.slot_id));

        if (outcome === "no-slot") {
          return notFound("Слот не найден");
        }

        if (outcome === "full") {
          return conflict("В этом окне мест больше нет");
        }

        return ok(accessRequestItem(found));
      }),
    ],
  },
];
