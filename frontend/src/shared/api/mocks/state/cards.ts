import type { components } from "../../schema/generated";

import {
  address,
  addressOf,
  demandTotal,
  isDemandSent,
  type MockFlat,
  type MockHouse,
} from "./houses";
import { flatMeters } from "./meters";
import {
  latestVerification,
  residencies,
  residencyForHouse,
  residencySummary,
  type MockResidency,
} from "./profile";

type Schemas = components["schemas"];

export const houseCard = (house: MockHouse): Schemas["HouseCard"] => {
  const residency = residencyForHouse(house.id);

  return {
    id: house.id,
    address: address(house),
    region: house.region,
    city: house.city,
    street: house.street,
    building: house.building,
    cadastral_no: house.cadastral_no,
    entrances: house.entrances,
    is_connected: house.is_connected,
    demand_count: demandTotal(house.id),
    demand_sent: isDemandSent(house.id),
    built_year: house.built_year,
    floors: house.floors,
    area: house.area,
    lat: house.lat,
    lon: house.lon,
    org: house.org,
    my_residency: residency ? residencySummary(residency) : null,
    chat_binding_code: null,
    chat_bound: false,
    overhaul: null,
    documents: [],
    outages: [
      {
        resource: "hot_water",
        reason: "Плановая промывка системы горячего водоснабжения",
        company: "Демо-РСО",
        starts_at: new Date(Date.now() - 3_600_000).toISOString(),
        ends_at: new Date(Date.now() + 6 * 3_600_000).toISOString(),
        recalc_hint:
          "Перерыв в ГВС дольше 4 ч подряд или 8 ч за месяц, не считая ежегодной профилактики, срок которой задают санитарные правила: плата за месяц снижается на 0,15% за каждый час сверх нормы (ПП 354, прил. 1, п. 4). Это оценка, не юридическая консультация",
        is_demo: true,
      },
    ],
    services: [
      {
        kind: "edds",
        name: "Единая дежурно-диспетчерская служба Казани",
        phone: "+7 (843) 236-41-23",
        note: "Короткий номер 063",
      },
      {
        kind: "water",
        name: "МУП «Водоканал»",
        phone: "+7 (843) 231-62-60",
        site: "https://www.kznvodokanal.ru",
        note: "Аварийно-диспетчерская служба",
      },
      {
        kind: "heat",
        name: "АО «Татэнерго»",
        phone: "8 (800) 234-82-43",
        site: "https://www.tatenergo.ru",
        note: "Теплоснабжающих организаций в городе несколько, ваша указана в квитанции",
      },
      {
        kind: "energy",
        name: "АО «Татэнергосбыт»",
        phone: "8 (800) 200-25-26",
        hours: "Пн-пт 8:00-19:00, сб 8:00-17:00",
        site: "https://tatenergosbyt.ru",
        note: "Ваш поставщик указан в квитанции за свет",
      },
      {
        kind: "gas",
        name: "ЭПУ «Казаньгоргаз» ООО «Газпром трансгаз Казань»",
        phone: "+7 (843) 292-58-85",
        site: "https://kazan-tr.gazprom.ru",
        note: "При запахе газа - сразу 104",
      },
      {
        kind: "waste",
        name: "Региональный оператор по обращению с отходами",
        phone: "+7 (843) 260-02-40",
        note: "Если не вывозят контейнеры по графику",
      },
      {
        kind: "gzhi",
        name: "Государственная жилищная инспекция Республики Татарстан",
        phone: "+7 (843) 222-02-77",
        site: "https://gji.tatarstan.ru",
      },
    ],
    org_stats: house.is_connected
      ? {
          closed: 38,
          on_time: 23,
          on_time_share: 6053,
          accept_time: 43,
          rating: 450,
          ratings_count: 22,
        }
      : null,
    passport: {
      reforma_on: "2026-09-01",
      entrances_estimated: false,
      energy_class: "B",
      wear: 3000,
      wear_on: "2021-08-01",
      condition: null,
      gis_on: "2026-09-28",
    },
  };
};

export const flatCard = (
  flat: MockFlat,
  residency: MockResidency,
): Schemas["FlatCard"] => {
  const canSeeCharges = residency.role === "owner";

  return {
    id: flat.id,
    house_id: flat.house_id,
    address: addressOf(flat.house_id),
    number: flat.number,
    role: residency.role,
    verified: residency.verified,
    can_see_charges: canSeeCharges,
    can_vote: canSeeCharges,
    meters_count: flatMeters(flat.id).length,
    residents_count: residencies().filter((item) => item.flat_id === flat.id)
      .length,
    entrance: flat.entrance,
    area: flat.area,
    account_no:
      residency.verified && canSeeCharges ? flat.account_no.slice(-4) : null,
    verification_status: latestVerification(flat.id)?.status ?? null,
  };
};
