import type { components } from "../schema/generated";

import { houseResidents } from "./admin-houses";
import { badRequest, demoLocked, endpoint, notFound, ok } from "./reply";
import {
  accessRequestGrid,
  createAccessRequest,
  findAccessRequest,
  orgAccessRequests,
  orgAppointments,
  receptionWindows,
  setReceptionWindows,
  todayIso,
  ZHILSERVIS,
} from "./state";

type Schemas = components["schemas"];

const ORG_ID = 1;

const windowError = (
  window: Schemas["ReceptionWindowInput"],
): string | null => {
  if (window.weekday < 0 || window.weekday > 6) {
    return "День недели вне диапазона";
  }

  if (window.time_from >= window.time_to) {
    return "Начало приема позже конца";
  }

  if (window.slot_minutes < 5 || window.slot_minutes > 240) {
    return "Длина слота от 5 до 240 минут";
  }

  return window.capacity < 1
    ? "В слот должен помещаться хотя бы один житель"
    : null;
};

const createError = (
  body: Schemas["CreateAccessRequestRequest"],
): string | null => {
  const starts = body.slots.map((slot) => slot.starts_at);

  if (!body.reason.trim()) {
    return "Напишите, зачем нужен доступ в квартиру";
  }

  if (body.slots.length === 0) {
    return "Добавьте хотя бы одно окно";
  }

  if (body.flat_ids.length === 0) {
    return "Выберите хотя бы одну квартиру";
  }

  if (body.slots.some((slot) => slot.capacity < 1)) {
    return "В окно должна помещаться хотя бы одна квартира";
  }

  if (body.date < todayIso()) {
    return "День доступа уже прошел";
  }

  if (new Set(starts).size !== starts.length) {
    return "Окна доступа начинаются в одно и то же время";
  }

  return starts.some((start) => start.slice(0, 10) !== body.date)
    ? "Окна доступа должны быть в тот же день"
    : null;
};

export const adminReceptionConfigs = [
  endpoint("get", "/admin/appointments", (request) =>
    ok(orgAppointments(ORG_ID, request.query.on_date ?? todayIso())),
  ),
  endpoint("get", "/admin/reception/windows", () =>
    ok(receptionWindows(ORG_ID)),
  ),
  endpoint("put", "/admin/reception/windows", (request) => {
    if (ZHILSERVIS.is_demo) {
      return demoLocked;
    }

    const body = request.body as Schemas["SetReceptionWindowsRequest"];
    const invalid = body.windows.map(windowError).find(Boolean);

    if (invalid) {
      return badRequest(invalid);
    }

    return ok(setReceptionWindows(ORG_ID, body.windows));
  }),
  endpoint("get", "/admin/access-requests", () =>
    ok(orgAccessRequests(ORG_ID)),
  ),
  endpoint("get", "/admin/access-requests/:access_request_id", (request) => {
    const found = findAccessRequest(Number(request.params.access_request_id));

    return found
      ? ok(accessRequestGrid(found))
      : notFound("Запрос доступа не найден");
  }),
  endpoint("post", "/admin/access-requests", (request) => {
    const body = request.body as Schemas["CreateAccessRequestRequest"];
    const invalid = createError(body);

    if (invalid) {
      return badRequest(invalid);
    }

    const eligible = new Map<
      number,
      { flat_id: number; flat_number: string }
    >();

    for (const resident of houseResidents(body.house_id)) {
      const { flat_id, flat_number } = resident;

      if (
        resident.verified &&
        resident.status !== "blocked" &&
        flat_id != null &&
        flat_number != null &&
        body.flat_ids.includes(flat_id) &&
        !eligible.has(flat_id)
      ) {
        eligible.set(flat_id, { flat_id, flat_number });
      }
    }

    return ok(createAccessRequest(body, [...eligible.values()]));
  }),
];
