import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  endpoint,
  notFound,
  ok,
  page,
  type MockHttpRequest,
} from "./reply";
import { addressOf, days, findHouse, houseFlats, period } from "./state";

type Schemas = components["schemas"];

type Resident = Schemas["HouseResidentItem"];

type Reading = Schemas["AdminReadingItem"];

const ORG_HOUSES = [
  {
    id: 1,
    flats_count: 120,
    residents_count: 86,
    open_requests: 7,
    chat_bound: true,
  },
  {
    id: 2,
    flats_count: 64,
    residents_count: 31,
    open_requests: 2,
    chat_bound: false,
  },
  {
    id: 3,
    flats_count: 96,
    residents_count: 12,
    open_requests: 0,
    chat_bound: true,
  },
];

const BOT_LINK = "https://max.ru/zheka_bot?start=";

const CHAT_TITLES: Record<number, string> = {
  1: "Баумана 12 - соседи",
  3: "ЖК на Баумана 16, официальный чат жильцов дома",
};

const PENDING_VERIFICATIONS: Record<number, number> = { 1: 3, 2: 2, 3: 3 };

const bindingCodes: Record<number, string> = {
  1: "a3f91c07",
  2: "5be20d4a",
  3: "0c7d18e2",
};

const NAMES = [
  "Алексей Иванов",
  "Мария Смирнова",
  "Ильдар Хабибуллин",
  "Елена Попова",
  "Дмитрий Васильев",
  "Светлана Зайцева",
  "Руслан Шарипов",
  "Наталья Соколова",
  "Артём Николаев",
  "Лейсан Гарипова",
  "Олег Фёдоров",
  "Татьяна Орлова",
  "Андрей Павлов",
];

type Seed = Pick<Resident, "name" | "flat_number"> & Partial<Resident>;

const HAND_MADE: Record<number, Seed[]> = {
  1: [
    { name: "Марат Галиев", flat_number: "112", is_chairman: true },
    { name: "Анна Морозова", flat_number: "45" },
    { name: "Игорь Тимофеев", flat_number: "7", verified: false },
    {
      name: "Гульнара Ахметзяновна Сафиуллина-Валиева",
      flat_number: "12",
      verified: false,
    },
    {
      name: "Сергей Кузнецов",
      flat_number: "28",
      role: "tenant",
      status: "blocked",
      block_reason:
        "Выкладывал в чат дома чужие персональные данные после двух предупреждений",
    },
    { name: "Ольга Белова", flat_number: "90", verified: false },
    { name: "Кирилл Лебедев", flat_number: "45", role: "tenant" },
  ],
  2: [
    { name: "Пётр Сергеев", flat_number: "3", verified: false },
    { name: "Денис Лапшин", flat_number: "56", verified: false },
  ],
  3: [
    { name: "Алла Гринёва", flat_number: "118", verified: false },
    { name: "Рустем Хайруллин", flat_number: "33", is_chairman: true },
  ],
};

const residents = new Map(
  ORG_HOUSES.map((house): [number, Resident[]] => {
    const seeds: Seed[] = [...HAND_MADE[house.id]];

    for (let index = seeds.length; index < house.residents_count; index += 1) {
      seeds.push({
        name: NAMES[index % NAMES.length],
        flat_number: String(((index * 7) % house.flats_count) + 1),
        role: index % 6 === 0 ? "tenant" : "owner",
        verified: index % 5 !== 0,
      });
    }

    return [
      house.id,
      seeds.map((seed, index) => ({
        resident_id: house.id * 1000 + index + 1,
        user_id: house.id * 1000 + index + 501,
        created_at: days(index - house.residents_count),
        role: "owner",
        status: "active",
        verified: true,
        is_chairman: false,
        flat_id: seed.flat_number
          ? (houseFlats(house.id, seed.flat_number)[0]?.id ?? null)
          : null,
        block_reason: null,
        ...seed,
      })),
    ];
  }),
);

const findResident = (request: MockHttpRequest) =>
  [...residents.values()]
    .flat()
    .find(
      (resident) => resident.resident_id === Number(request.params.resident_id),
    );

export const houseResidents = (houseId: number): Resident[] =>
  residents.get(houseId) ?? [];

const orgHouse = (request: MockHttpRequest) =>
  ORG_HOUSES.find((house) => house.id === Number(request.params.house_id));

const READING_FLATS = [
  { number: "7", by: "Игорь Тимофеев" },
  { number: "12", by: "Гульнара Сафиуллина-Валиева" },
  { number: "28", by: "Сергей Кузнецов" },
  { number: "45", by: "Анна Морозова" },
  { number: "90", by: "Ольга Белова" },
  { number: "112", by: "Марат Галиев" },
];

const READING_METERS: {
  type: Schemas["MeterType"];
  zones: string[];
  base: number;
  step: number;
}[] = [
  { type: "cold_water", zones: ["single"], base: 312_400, step: 6_200 },
  { type: "hot_water", zones: ["single"], base: 184_900, step: 3_800 },
  {
    type: "electricity",
    zones: ["day", "night"],
    base: 8_415_000,
    step: 142_000,
  },
];

const houseReadings: Reading[] = READING_FLATS.flatMap((flat, flatIndex) =>
  READING_METERS.flatMap((meter, meterIndex) =>
    [2, 1, 0].map((monthsBack): Reading => {
      const serial = `${meterIndex + 1}${flat.number.padStart(4, "0")}${flatIndex}`;
      const month = 3 - monthsBack;
      const below =
        flat.number === "28" && meter.type === "cold_water" && monthsBack === 1;
      const total =
        meter.base * (flatIndex + 1) + meter.step * (below ? month - 2 : month);
      const byZone = (amount: number) =>
        Object.fromEntries(
          meter.zones.map((zone, index) => [
            zone,
            index === 0 ? amount : Math.round(amount * 0.4),
          ]),
        );
      const id = 90_000 + flatIndex * 100 + meterIndex * 10 + monthsBack;

      return {
        id,
        meter_id: 7000 + flatIndex * 10 + meterIndex,
        meter_type: meter.type,
        serial,
        flat_id: 1000 + Number(flat.number),
        flat_number: flat.number,
        period: period(monthsBack),
        values: byZone(total),
        consumption: byZone(below ? -meter.step : meter.step),
        photos: [],
        is_below_previous: below,
        ocr_used: (flatIndex + meterIndex) % 3 === 0,
        submitted_at: new Date(
          Date.parse(period(monthsBack)) +
            (14 + ((flatIndex + meterIndex) % 5)) * 24 * 60 * 60 * 1000 +
            flatIndex * 60 * 60 * 1000,
        ).toISOString(),
        submitted_by_name: flat.by,
      };
    }),
  ),
).sort((a, b) => b.submitted_at.localeCompare(a.submitted_at));

const reasonOf = (body: Record<string, unknown>) =>
  typeof body.reason === "string" ? body.reason.trim() : "";

export const adminHousesConfigs = [
  endpoint("get", "/admin/houses", (request) => {
    const query = (request.query.q ?? "").trim().toLowerCase();

    return ok(
      page(
        ORG_HOUSES.map((item) => ({
          ...item,
          address: addressOf(item.id),
          entrances: findHouse(item.id)!.entrances,
        })).filter((item) => item.address.toLowerCase().includes(query)),
        request.query,
        50,
      ) satisfies Schemas["Page_AdminHouseListItem_"],
    );
  }),
  endpoint("get", "/admin/houses/:house_id", (request) => {
    const item = orgHouse(request);

    if (!item) {
      return notFound("Дом не найден");
    }

    const house = findHouse(item.id)!;
    const list = houseResidents(item.id);

    return ok({
      id: house.id,
      address: addressOf(house.id),
      region: house.region,
      city: house.city,
      street: house.street,
      building: house.building,
      cadastral_no: house.cadastral_no,
      entrances: house.entrances,
      flats_count: item.flats_count,
      residents_count: list.length,
      verified_residents_count: list.filter((resident) => resident.verified)
        .length,
      pending_verifications: PENDING_VERIFICATIONS[house.id],
      open_requests: item.open_requests,
      chat_bound: item.chat_bound,
      chat_binding_code: bindingCodes[house.id],
      entrance_qrs: Array.from({ length: house.entrances }, (_, index) => ({
        entrance: index + 1,
        code: `qr_${house.id}_${index + 1}`,
        deeplink: `${BOT_LINK}qr_${house.id}_${index + 1}`,
      })),
      built_year: house.built_year,
      floors: house.floors,
      area: house.area,
      chairman_name:
        list.find((resident) => resident.is_chairman)?.name ?? null,
      chat_title: item.chat_bound ? CHAT_TITLES[house.id] : null,
    } satisfies Schemas["AdminHouseCard"]);
  }),
  endpoint("post", "/admin/houses/:house_id/binding-code", (request) => {
    const item = orgHouse(request);

    if (!item) {
      return notFound("Дом не найден");
    }

    const code = Array.from({ length: 8 }, () =>
      Math.floor(Math.random() * 16).toString(16),
    ).join("");
    bindingCodes[item.id] = code;

    return ok({
      house_id: item.id,
      code,
      deeplink: `${BOT_LINK}house_${item.id}`,
    } satisfies Schemas["BindingCodeResponse"]);
  }),
  endpoint("get", "/admin/houses/:house_id/residents", (request) => {
    const item = orgHouse(request);

    if (!item) {
      return notFound("Дом не найден");
    }

    const query = (request.query.q ?? "").trim().toLowerCase();

    return ok(
      page(
        houseResidents(item.id).filter(
          (resident) =>
            resident.name.toLowerCase().includes(query) ||
            (resident.flat_number ?? "").toLowerCase().startsWith(query),
        ),
        request.query,
        50,
      ) satisfies Schemas["Page_HouseResidentItem_"],
    );
  }),
  endpoint("get", "/admin/houses/:house_id/readings", (request) => {
    const item = orgHouse(request);

    if (!item) {
      return notFound("Дом не найден");
    }

    const { query } = request;

    return ok(
      page(
        (item.id === 1 ? houseReadings : []).filter(
          (reading) =>
            (query.only_below_previous !== "true" ||
              reading.is_below_previous) &&
            (query.period === undefined || reading.period === query.period) &&
            (query.meter_type === undefined ||
              reading.meter_type === query.meter_type),
        ),
        query,
        50,
      ) satisfies Schemas["Page_AdminReadingItem_"],
    );
  }),
  endpoint("post", "/admin/residents/:resident_id/block", (request) => {
    const reason = reasonOf(request.body);

    if (!reason) {
      return badRequest("Укажите причину");
    }

    const resident = findResident(request);

    if (!resident) {
      return notFound("Житель не найден");
    }

    if (resident.is_chairman) {
      return conflict("Нельзя заблокировать председателя совета дома");
    }

    resident.status = "blocked";
    resident.block_reason = reason;

    return ok(resident);
  }),
  endpoint("post", "/admin/residents/:resident_id/unblock", (request) => {
    const resident = findResident(request);

    if (!resident) {
      return notFound("Житель не найден");
    }

    resident.status = "active";
    resident.block_reason = null;

    return ok(resident);
  }),
  endpoint(
    "post",
    "/admin/residents/:resident_id/revoke-verification",
    (request) => {
      const reason = reasonOf(request.body);

      if (!reason) {
        return badRequest("Укажите причину");
      }

      const resident = findResident(request);

      if (!resident) {
        return notFound("Житель не найден");
      }

      if (!resident.verified) {
        return conflict("Квартира жителя не подтверждена");
      }

      resident.verified = false;

      return ok(resident);
    },
  ),
  endpoint("post", "/admin/residents/:resident_id/chairman", (request) => {
    const resident = findResident(request);

    if (!resident) {
      return notFound("Житель не найден");
    }

    if (request.body.is_chairman === true) {
      if (!resident.verified) {
        return conflict(
          "Председателем становится житель с подтвержденной квартирой",
        );
      }

      for (const neighbour of houseResidents(
        Math.floor(resident.resident_id / 1000),
      )) {
        neighbour.is_chairman = false;
      }
    }

    resident.is_chairman = request.body.is_chairman === true;

    return ok(resident);
  }),
];
