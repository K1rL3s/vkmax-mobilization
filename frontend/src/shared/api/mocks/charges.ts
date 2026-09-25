import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  endpoint,
  forbidden,
  isReply,
  notFound,
  number,
  ok,
  page,
  type MockHttpRequest,
  type Reply,
} from "./reply";
import {
  HOUSE_AVERAGE,
  addressOf,
  createRequest,
  findFlat,
  findHouse,
  flatMeters,
  period,
  residencyForFlat,
  residencyForHouse,
  type MockFlat,
} from "./state";

type Schemas = components["schemas"];

type Service = Schemas["ServiceType"];

type Found = { id: number; flat: MockFlat; monthsBack: number };

const HISTORY = 6;

const TARIFF: Record<string, [old: number, current: number]> = {
  cold_water: [350000, 384000],
  hot_water: [1980000, 2125000],
  electricity: [52400, 56200],
  heating: [24500000, 24500000],
  maintenance: [289000, 289000],
};

const VOLUME: Record<string, number[]> = {
  cold_water: [5200, 4800, 4100, 4300, 4500, 4600],
  hot_water: [3600, 3300, 2900, 3000, 3100, 3200],
  electricity: [182000, 168000, 150000, 171000, 176000, 190000],
};

const METERED = ["cold_water", "hot_water", "electricity"] as const;

const UNIT: Record<string, string> = {
  cold_water: "м³",
  hot_water: "м³",
  electricity: "кВт·ч",
  heating: "Гкал",
  maintenance: "м²",
};

const LABEL: Record<Service, string> = {
  cold_water: "Холодная вода",
  hot_water: "Горячая вода",
  electricity: "Электроэнергия",
  gas: "Газ",
  heating: "Отопление",
  maintenance: "Содержание жилья",
  overhaul: "Капитальный ремонт",
  waste: "Обращение с ТКО",
  penalty: "Пени",
  recalculation: "Перерасчёт",
};

const paidAt = new Map<number, string>();

const kopecks = (volume: number, tariff: number) =>
  Math.round((volume * tariff) / 100000);

const metered = (
  service: Service,
  volume: number,
  monthsBack: number,
): Schemas["ChargeLine"] => {
  const [old, current] = TARIFF[service];
  const tariff = monthsBack <= 2 ? current : old;

  return {
    service,
    label: LABEL[service],
    amount: kopecks(volume, tariff),
    volume,
    tariff,
    unit: UNIT[service],
  };
};

const lines = ({
  flat,
  monthsBack,
}: Omit<Found, "id">): Schemas["ChargeLine"][] => [
  ...METERED.map((service) =>
    metered(service, VOLUME[service][monthsBack] ?? 0, monthsBack),
  ),
  ...(monthsBack === 0 ? [metered("heating", 450, monthsBack)] : []),
  metered("maintenance", (flat.area ?? 5000) * 10, monthsBack),
  { service: "overhaul", label: LABEL.overhaul, amount: 118000 },
  { service: "waste", label: LABEL.waste, amount: 42000 },
];

const total = (items: Schemas["ChargeLine"][]) =>
  items.reduce((sum, line) => sum + line.amount, 0);

const paid = ({ id, monthsBack }: Found) =>
  paidAt.get(id) ??
  (monthsBack >= 2
    ? `${period(monthsBack - 1).slice(0, 8)}10T09:00:00Z`
    : null);

const listItem = (found: Found): Schemas["ChargeListItem"] => ({
  id: found.id,
  flat_id: found.flat.id,
  period: period(found.monthsBack),
  total: total(lines(found)),
  is_closed: true,
  paid_at: paid(found),
});

const flatAccess = (flatId: number) => {
  const residency = residencyForFlat(flatId);

  if (!residency) {
    return notFound("Квартира не найдена");
  }

  if (!residency.verified) {
    return forbidden("Подтвердите квартиру, чтобы видеть начисления");
  }

  return residency.role === "owner"
    ? null
    : forbidden("Начисления недоступны для вашей роли");
};

const breakdown = (found: Found): Schemas["ChargeBreakdown"] => {
  const current = lines(found);
  const hasPrevious = found.monthsBack + 1 < HISTORY;
  const previous = hasPrevious
    ? lines({ flat: found.flat, monthsBack: found.monthsBack + 1 })
    : [];
  const services = [
    ...current.map((line) => line.service),
    ...previous
      .map((line) => line.service)
      .filter((service) => !current.some((line) => line.service === service)),
  ];
  const meters = flatMeters(found.flat.id);

  return {
    charge_id: found.id,
    period: period(found.monthsBack),
    total: total(current),
    delta: total(current) - total(previous),
    lines: services
      .map((service) => {
        const now = current.find((line) => line.service === service);
        const before = previous.find((line) => line.service === service);
        const delta = (now?.amount ?? 0) - (before?.amount ?? 0);
        const tariffEffect =
          now?.volume != null &&
          now.tariff != null &&
          before?.tariff != null &&
          before.volume != null
            ? kopecks(now.volume, now.tariff - before.tariff)
            : 0;

        return {
          service,
          label: LABEL[service],
          amount: now?.amount ?? 0,
          delta,
          tariff_effect: tariffEffect,
          volume_effect: delta - tariffEffect,
          appeared: !before,
          disappeared: !now,
          previous_amount: before?.amount ?? null,
        };
      })
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)),
    previous_period: hasPrevious ? period(found.monthsBack + 1) : null,
    previous_total: hasPrevious ? total(previous) : null,
    consumption: METERED.map((service) => ({
      service,
      meter_id: meters.find((meter) => meter.type === service)?.id ?? 0,
      points: Array.from(
        { length: HISTORY - found.monthsBack },
        (_, index) => found.monthsBack + index,
      )
        .reverse()
        .map((monthsBack) => ({
          period: period(monthsBack),
          consumption: VOLUME[service][monthsBack] ?? 0,
        })),
      house_average: HOUSE_AVERAGE[service],
    })),
  };
};

const chargeAccess = (request: MockHttpRequest): Found | Reply => {
  const id = number(request.params.charge_id);
  const flat = id === null ? undefined : findFlat(Math.floor(id / 100));

  if (id === null || !flat || id % 100 >= HISTORY) {
    return notFound("Квитанция не найдена");
  }

  return flatAccess(flat.id) ?? { id, flat, monthsBack: id % 100 };
};

const TARIFFS = (
  [
    [6, "cold_water", 384000, "2026-07-01"],
    [7, "hot_water", 2125000, "2026-07-01"],
    [8, "electricity", 56200, "2026-07-01"],
    [1, "cold_water", 351000, "2025-07-01"],
    [2, "hot_water", 1980000, "2025-07-01"],
    [3, "electricity", 52100, "2025-07-01"],
    [4, "heating", 24500000, "2025-07-01"],
    [5, "maintenance", 289000, "2025-07-01"],
  ] as const
).map(([id, service, value, validFrom]): Schemas["TariffItem"] => ({
  id,
  service,
  label: LABEL[service],
  value,
  unit: UNIT[service],
  valid_from: validFrom,
  document: null,
}));

export const chargesConfigs = [
  endpoint("get", "/flats/:flat_id/charges", (request) => {
    const flat = findFlat(Number(request.params.flat_id));

    if (!flat) {
      return notFound("Квартира не найдена");
    }

    return (
      flatAccess(flat.id) ??
      ok(
        page(
          Array.from({ length: HISTORY }, (_, monthsBack) =>
            listItem({ id: flat.id * 100 + monthsBack, flat, monthsBack }),
          ),
          request.query,
          50,
        ) satisfies Schemas["Page_ChargeListItem_"],
      )
    );
  }),
  endpoint("get", "/charges/:charge_id", (request) => {
    const found = chargeAccess(request);

    return isReply(found)
      ? found
      : ok({
          ...listItem(found),
          address: addressOf(found.flat.house_id),
          flat_number: found.flat.number,
          lines: lines(found),
          flat_area: found.flat.area,
        } satisfies Schemas["ChargeCard"]);
  }),
  endpoint("get", "/charges/:charge_id/breakdown", (request) => {
    const found = chargeAccess(request);

    return isReply(found) ? found : ok(breakdown(found));
  }),
  endpoint("post", "/charges/:charge_id/dispute", (request) => {
    const found = chargeAccess(request);

    if (isReply(found)) {
      return found;
    }

    const comment = (request.body as Schemas["DisputeChargeRequest"]).comment;

    if (typeof comment !== "string") {
      return badRequest("Нужен комментарий");
    }

    const { delta } = breakdown(found);
    const [year, month] = period(found.monthsBack).split("-");
    const created = createRequest(found.flat.house_id, {
      category: "charge_dispute",
      description: `Начисление за ${month}.${year} изменилось на ${delta < 0 ? "-" : "+"}${(Math.abs(delta) / 100).toFixed(2)} руб.\n\n${comment.trim()}`,
      flat_id: found.flat.id,
      photos: [],
      llm_suggested: false,
      llm_accepted: false,
    });

    return ok({
      request_id: created.id,
    } satisfies Schemas["DisputeChargeResponse"]);
  }),
  endpoint("post", "/charges/:charge_id/pay", (request) => {
    const found = chargeAccess(request);

    if (isReply(found)) {
      return found;
    }

    if (paid(found) !== null) {
      return conflict("Квитанция уже оплачена");
    }

    const at = new Date().toISOString();
    paidAt.set(found.id, at);

    return ok({
      charge_id: found.id,
      paid_at: at,
      is_demo: true,
    } satisfies Schemas["PayChargeResponse"]);
  }),
  endpoint("get", "/houses/:house_id/tariffs", (request) => {
    const house = findHouse(Number(request.params.house_id));

    if (!house || !residencyForHouse(house.id)) {
      return notFound("Дом не найден");
    }

    return ok(house.is_connected ? TARIFFS : []);
  }),
];
