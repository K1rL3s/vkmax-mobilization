import type { components } from "../schema/generated";

import { houseResidents } from "./admin-houses";
import { badRequest, notFound, ok, route } from "./reply";
import {
  accessRequestGrid,
  createAccessRequest,
  findAccessRequest,
  orgAccessRequests,
  orgAppointments,
  receptionWindows,
  setReceptionWindows,
  todayIso,
} from "./state";

type Schemas = components["schemas"];

// X-Org-Id мок не сверяет, как и остальные админские файлы: кабинет работает
// с «Жилсервисом», чьи дома, заявки и часы приёма лежат в посеве. Иначе
// переключение организации уводило бы часы в пустую сетку чужой УК
const ORG_ID = 1;

// границы - из ReceptionService.set_windows бэка: окно внутри суток, слот от
// пяти минут до четырёх часов и не длиннее самого окна
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

// границы - из AccessService.create бэка: причина непустая, окна и квартиры
// есть, в окно помещается хотя бы одна квартира, день не прошёл, окна не
// повторяются и все лежат в этом дне
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
  {
    path: "/admin/appointments" as const,
    method: "get" as const,
    routes: [
      route((request) =>
        // «без даты - на сегодня», как написано в контракте
        ok(orgAppointments(ORG_ID, request.query.on_date ?? todayIso())),
      ),
    ],
  },
  {
    path: "/admin/reception/windows" as const,
    method: "get" as const,
    routes: [route(() => ok(receptionWindows(ORG_ID)))],
  },
  {
    path: "/admin/reception/windows" as const,
    method: "put" as const,
    routes: [
      route((request) => {
        const body = request.body as Schemas["SetReceptionWindowsRequest"];
        const invalid = body.windows.map(windowError).find(Boolean);

        if (invalid) {
          return badRequest(invalid);
        }

        return ok(setReceptionWindows(ORG_ID, body.windows));
      }),
    ],
  },
  {
    path: "/admin/access-requests" as const,
    method: "get" as const,
    routes: [route(() => ok(orgAccessRequests(ORG_ID)))],
  },
  {
    path: "/admin/access-requests/:access_request_id" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const found = findAccessRequest(
          Number(request.params.access_request_id),
        );

        // квартиры без ячейки бэк отдаёт только в ответе на создание: чтение
        // сбора возвращает пустой список, и карточка их больше не показывает
        return found
          ? ok(accessRequestGrid(found))
          : notFound("Запрос доступа не найден");
      }),
    ],
  },
  {
    path: "/admin/access-requests" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const body = request.body as Schemas["CreateAccessRequestRequest"];
        const invalid = createError(body);

        if (invalid) {
          return badRequest(invalid);
        }

        // предикат бэка: ячейку получает квартира с подтверждённым и не
        // заблокированным жителем. Жители лежат в файле «Домов», поэтому
        // считает его ручка, а не состояние
        const eligible = new Map<
          number,
          { flat_id: number; flat_number: string }
        >();

        for (const resident of houseResidents(body.house_id)) {
          const { flat_id: flatId, flat_number: flatNumber } = resident;

          if (
            resident.verified &&
            resident.status !== "blocked" &&
            flatId != null &&
            flatNumber != null &&
            body.flat_ids.includes(flatId) &&
            !eligible.has(flatId)
          ) {
            eligible.set(flatId, {
              flat_id: flatId,
              flat_number: flatNumber,
            });
          }
        }

        return ok(createAccessRequest(body, [...eligible.values()]));
      }),
    ],
  },
];
