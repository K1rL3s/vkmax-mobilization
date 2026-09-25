import type { components } from "../schema/generated";

import { conflict, endpoint, forbidden, houseOf, notFound, ok } from "./reply";
import {
  accessRequestItem,
  bookAppointment,
  chooseAccessSlot,
  findAccessRequest,
  findAppointment,
  findHouse,
  houseAccessRequests,
  houseRequests,
  myAppointments,
  receptionSlots,
  residencyForHouse,
} from "./state";

type Schemas = components["schemas"];

export const appointmentsConfigs = [
  endpoint("get", "/houses/:house_id/reception-slots", (request) => {
    const houseId = Number(request.params.house_id);

    if (!findHouse(houseId)) {
      return notFound("Дом не найден");
    }

    return residencyForHouse(houseId)
      ? ok(receptionSlots(houseId, request.query.on_date))
      : forbidden("Вы не живёте в этом доме");
  }),
  endpoint("get", "/appointments", () => ok(myAppointments())),
  endpoint("post", "/appointments", (request) => {
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
  endpoint("delete", "/appointments/:appointment_id", (request) => {
    const found = findAppointment(Number(request.params.appointment_id));

    if (!found) {
      return notFound("Запись не найдена");
    }

    if (found.status === "done") {
      return conflict("Прием уже прошел");
    }

    found.status = "cancelled";

    return ok({ ok: true } satisfies Schemas["OkResponse"]);
  }),
  endpoint("get", "/access-requests", (request) => {
    const houseId = houseOf(request);

    return ok(
      houseId !== null && residencyForHouse(houseId)
        ? houseAccessRequests(houseId)
        : [],
    );
  }),
  endpoint(
    "post",
    "/access-requests/:access_request_id/slots/:slot_id",
    (request) => {
      const found = findAccessRequest(Number(request.params.access_request_id));

      if (!found || !residencyForHouse(found.house_id)?.verified) {
        return notFound("Запрос доступа не найден");
      }

      const outcome = chooseAccessSlot(found, Number(request.params.slot_id));

      if (outcome === "no-slot") {
        return notFound("Слот не найден");
      }

      return outcome === "full"
        ? conflict("В этом окне мест больше нет")
        : ok(accessRequestItem(found));
    },
  ),
];
