import {
  badRequest,
  conflict,
  fail,
  notFound,
  number,
  ok,
  route,
} from "./reply";
import {
  addResidency,
  demandTotal,
  findFlat,
  findHouse,
  flatListItem,
  houseCard,
  houseFlats,
  houseListItem,
  removeResidency,
  residencySummary,
  residencyForHouse,
  searchHouses,
  signalDemand,
} from "./state";

// «Ошибка» в поиске - способ увидеть экран ошибки, не выключая мок
const ERROR_QUERY = "ошибка";

export const housesConfigs = [
  {
    path: "/houses" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const query = request.query.q ?? request.query.street ?? "";

        if (query.trim().toLowerCase() === ERROR_QUERY) {
          return fail(500, "Внутренняя ошибка сервера", "Что-то пошло не так");
        }

        const limit = number(request.query.limit) ?? 20;
        const offset = number(request.query.offset) ?? 0;
        const found = searchHouses(query);

        return ok({
          items: found.slice(offset, offset + limit).map(houseListItem),
          total: found.length,
        });
      }),
    ],
  },
  {
    path: "/houses/:house_id" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const house = findHouse(Number(request.params.house_id));

        return house ? ok(houseCard(house)) : notFound("Дом не найден");
      }),
    ],
  },
  {
    path: "/houses/:house_id/flats" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const house = findHouse(Number(request.params.house_id));

        if (!house) {
          return notFound("Дом не найден");
        }

        const limit = number(request.query.limit) ?? 50;
        const offset = number(request.query.offset) ?? 0;
        const found = houseFlats(house.id, request.query.q ?? "");

        return ok({
          items: found.slice(offset, offset + limit).map(flatListItem),
          total: found.length,
        });
      }),
    ],
  },
  {
    path: "/houses/:house_id/link" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const house = findHouse(Number(request.params.house_id));

        if (!house) {
          return notFound("Дом не найден");
        }

        const { flat_id: flatId, flat_number: flatNumber } = request.body;

        if (flatId != null && flatNumber != null) {
          return badRequest("Укажите либо квартиру из списка, либо номер");
        }

        const existing = residencyForHouse(house.id);

        if (existing) {
          return ok(residencySummary(existing));
        }

        const flat = flatId == null ? null : (findFlat(Number(flatId)) ?? null);

        if (flatId != null && (!flat || flat.house_id !== house.id)) {
          return notFound("Квартира не найдена");
        }

        const role = request.body.role === "tenant" ? "tenant" : "owner";
        const residency = addResidency(
          house.id,
          flat,
          flatNumber == null ? null : String(flatNumber),
          role,
        );

        return ok(residencySummary(residency));
      }),
    ],
  },
  {
    path: "/residencies/:resident_id" as const,
    method: "delete" as const,
    routes: [
      route((request) =>
        removeResidency(Number(request.params.resident_id))
          ? ok({ ok: true })
          : notFound("Привязка к дому не найдена"),
      ),
    ],
  },
  {
    path: "/houses/:house_id/demand" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const house = findHouse(Number(request.params.house_id));

        if (!house) {
          return notFound("Дом не найден");
        }

        if (house.is_connected) {
          return conflict("УК этого дома уже подключена");
        }

        signalDemand(house.id);

        return ok({ house_id: house.id, total: demandTotal(house.id) });
      }),
    ],
  },
];
