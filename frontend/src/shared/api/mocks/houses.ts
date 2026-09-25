import {
  badRequest,
  conflict,
  endpoint,
  fail,
  notFound,
  ok,
  page,
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

export const housesConfigs = [
  endpoint("get", "/houses", (request) => {
    const query = request.query.q ?? request.query.street ?? "";

    return query.trim().toLowerCase() === "ошибка"
      ? fail(500, "Внутренняя ошибка сервера", "Что-то пошло не так")
      : ok(page(searchHouses(query).map(houseListItem), request.query));
  }),
  endpoint("get", "/houses/:house_id", (request) => {
    const house = findHouse(Number(request.params.house_id));

    return house ? ok(houseCard(house)) : notFound("Дом не найден");
  }),
  endpoint("get", "/houses/:house_id/flats", (request) => {
    const house = findHouse(Number(request.params.house_id));

    return house
      ? ok(
          page(
            houseFlats(house.id, request.query.q ?? "").map(flatListItem),
            request.query,
            50,
          ),
        )
      : notFound("Дом не найден");
  }),
  endpoint("post", "/houses/:house_id/link", (request) => {
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

    if (flatId != null && flat?.house_id !== house.id) {
      return notFound("Квартира не найдена");
    }

    return ok(
      residencySummary(
        addResidency(
          house.id,
          flat,
          flatNumber == null ? null : String(flatNumber),
          request.body.role === "tenant" ? "tenant" : "owner",
        ),
      ),
    );
  }),
  endpoint("delete", "/residencies/:resident_id", (request) =>
    removeResidency(Number(request.params.resident_id))
      ? ok({ ok: true })
      : notFound("Привязка к дому не найдена"),
  ),
  endpoint("post", "/houses/:house_id/demand", (request) => {
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
];
