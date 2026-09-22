import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  forbidden,
  notFound,
  number,
  ok,
  route,
} from "./reply";
import {
  address,
  createRequest,
  findFlat,
  findHouse,
  flatMeters,
  residencies,
} from "./state";

type Schemas = components["schemas"];

type Service = Schemas["ServiceType"];

// полгода истории: столько же точек у графика расхода на бэке
const HISTORY = 6;

// id квитанции собран из квартиры и сдвига месяца назад, так квитанции не
// нужно хранить: 10502 - квартира 105, позапрошлый месяц
const chargeId = (flatId: number, monthsBack: number) =>
  flatId * 100 + monthsBack;

const period = (monthsBack: number): string => {
  const today = new Date();
  const month = new Date(today.getFullYear(), today.getMonth() - monthsBack, 1);

  return `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-01`;
};

// тариф в 1/10000 рубля; индексация пришлась на позапрошлый месяц, чтобы
// разбор показал и вклад тарифа, и вклад расхода
const TARIFF: Record<string, [old: number, current: number]> = {
  cold_water: [350000, 384000],
  hot_water: [1980000, 2125000],
  electricity: [52400, 56200],
  heating: [24500000, 24500000],
  maintenance: [289000, 289000],
};

const INDEXED_SINCE = 2;

// расход в тысячных долях единицы по месяцам назад: [текущий, прошлый, ...]
const VOLUME: Record<string, number[]> = {
  cold_water: [5200, 4800, 4100, 4300, 4500, 4600],
  hot_water: [3600, 3300, 2900, 3000, 3100, 3200],
  electricity: [182000, 168000, 150000, 171000, 176000, 190000],
};

const HOUSE_AVERAGE: Partial<Record<Service, number>> = {
  cold_water: 4200,
  hot_water: 3100,
  electricity: 210000,
};

const METERED: Service[] = ["cold_water", "hot_water", "electricity"];

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

// оплату житель меняет демо-кнопкой, остальное выводится из месяца
const paidAt = new Map<number, string | null>();

// тысячные объёма * тариф (1/10000 рубля) дают 1/100000 копейки
const kopecks = (volume: number, tariff: number) =>
  Math.round((volume * tariff) / 100000);

const metered = (
  service: Service,
  volume: number,
  monthsBack: number,
): Schemas["ChargeLine"] => {
  const [old, current] = TARIFF[service] ?? [0, 0];
  const tariff = monthsBack <= INDEXED_SINCE ? current : old;

  return {
    service,
    label: LABEL[service],
    amount: kopecks(volume, tariff),
    volume,
    tariff,
    unit: UNIT[service] ?? null,
  };
};

const chargeLines = (
  flatArea: number,
  monthsBack: number,
): Schemas["ChargeLine"][] => [
  ...METERED.map((service) =>
    metered(service, VOLUME[service]?.[monthsBack] ?? 0, monthsBack),
  ),
  // отопительный сезон начался в текущем месяце: строка новая, разложить её
  // на тариф и расход нельзя
  ...(monthsBack === 0 ? [metered("heating", 450, monthsBack)] : []),
  metered("maintenance", flatArea * 10, monthsBack),
  { service: "overhaul", label: LABEL.overhaul, amount: 118000 },
  { service: "waste", label: LABEL.waste, amount: 42000 },
];

const findCharge = (rawChargeId: string) => {
  const id = number(rawChargeId);

  if (id === null) {
    return null;
  }

  const monthsBack = id % 100;
  const flat = findFlat(Math.floor(id / 100));

  return flat && monthsBack < HISTORY ? { id, flat, monthsBack } : null;
};

type Found = NonNullable<ReturnType<typeof findCharge>>;

const lines = ({ flat, monthsBack }: Pick<Found, "flat" | "monthsBack">) =>
  chargeLines(flat.area ?? 5000, monthsBack);

const total = (items: Schemas["ChargeLine"][]) =>
  items.reduce((sum, line) => sum + line.amount, 0);

// старые месяцы оплачены десятого числа следующего
const paid = ({ id, monthsBack }: Pick<Found, "id" | "monthsBack">) => {
  if (paidAt.has(id)) {
    return paidAt.get(id) ?? null;
  }

  return monthsBack >= 2
    ? `${period(monthsBack - 1).slice(0, 8)}10T09:00:00Z`
    : null;
};

const listItem = (found: Found): Schemas["ChargeListItem"] => ({
  id: found.id,
  flat_id: found.flat.id,
  period: period(found.monthsBack),
  total: total(lines(found)),
  is_closed: true,
  paid_at: paid(found),
});

// начисления видит только подтвержденный собственник: арендатору и
// неподтвержденному бэк отказывает, а не отдает пустой список
const flatAccess = (flatId: number) => {
  const residency = residencies().find((item) => item.flat_id === flatId);

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

  // целую строку бэк относит к расходу и ставит строки по размеру дельты
  const breakdownLines = services.map((service) => {
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
      label: (now ?? before)?.label ?? LABEL[service],
      amount: now?.amount ?? 0,
      delta,
      tariff_effect: tariffEffect,
      volume_effect: delta - tariffEffect,
      appeared: !before,
      disappeared: !now,
      previous_amount: before?.amount ?? null,
    };
  });
  breakdownLines.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  const meters = flatMeters(found.flat.id);

  return {
    charge_id: found.id,
    period: period(found.monthsBack),
    total: total(current),
    delta: total(current) - total(previous),
    lines: breakdownLines,
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
          consumption: VOLUME[service]?.[monthsBack] ?? 0,
        })),
      house_average: HOUSE_AVERAGE[service] ?? null,
    })),
  };
};

// квитанция доступна тем же, кому доступна ее квартира
const chargeAccess = (rawChargeId: string) => {
  const found = findCharge(rawChargeId);

  if (!found) {
    return { reply: notFound("Квитанция не найдена") };
  }

  const denied = flatAccess(found.flat.id);

  return denied ? { reply: denied } : { found };
};

export const chargesConfigs = [
  {
    path: "/flats/:flat_id/charges" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const flat = findFlat(Number(request.params.flat_id));

        if (!flat) {
          return notFound("Квартира не найдена");
        }

        const denied = flatAccess(flat.id);

        if (denied) {
          return denied;
        }

        const limit = number(request.query.limit) ?? 50;
        const offset = number(request.query.offset) ?? 0;
        const items = Array.from({ length: HISTORY }, (_, monthsBack) =>
          listItem({ id: chargeId(flat.id, monthsBack), flat, monthsBack }),
        );

        return ok({
          items: items.slice(offset, offset + limit),
          total: items.length,
        } satisfies Schemas["Page_ChargeListItem_"]);
      }),
    ],
  },
  {
    path: "/charges/:charge_id" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const { found, reply } = chargeAccess(request.params.charge_id);

        if (!found) {
          return reply;
        }

        const flat = found.flat;
        const items = lines(found);
        const house = findHouse(flat.house_id);

        return ok({
          ...listItem(found),
          address: house ? address(house) : "",
          flat_number: flat.number,
          lines: items,
          flat_area: flat.area,
        } satisfies Schemas["ChargeCard"]);
      }),
    ],
  },
  {
    path: "/charges/:charge_id/breakdown" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const { found, reply } = chargeAccess(request.params.charge_id);

        return found ? ok(breakdown(found)) : reply;
      }),
    ],
  },
  {
    path: "/charges/:charge_id/dispute" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const { found, reply } = chargeAccess(request.params.charge_id);

        if (!found) {
          return reply;
        }

        const body = request.body as Schemas["DisputeChargeRequest"];

        if (typeof body.comment !== "string") {
          return badRequest("Нужен комментарий");
        }

        const { delta } = breakdown(found);
        const [year, month] = period(found.monthsBack).split("-");
        const created = createRequest(found.flat.house_id, {
          category: "charge_dispute",
          description: `Начисление за ${month}.${year} изменилось на ${delta < 0 ? "-" : "+"}${(Math.abs(delta) / 100).toFixed(2)} руб.\n\n${body.comment.trim()}`,
          flat_id: found.flat.id,
          photos: [],
          llm_suggested: false,
          llm_accepted: false,
        });

        return ok({
          request_id: created.id,
        } satisfies Schemas["DisputeChargeResponse"]);
      }),
    ],
  },
  {
    path: "/charges/:charge_id/pay" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const { found, reply } = chargeAccess(request.params.charge_id);

        if (!found) {
          return reply;
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
    ],
  },
];
