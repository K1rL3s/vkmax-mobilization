import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  forbidden,
  notFound,
  ok,
  route,
  type Reply,
} from "./reply";
import {
  currentPeriod,
  findFlat,
  findMeter,
  flatMeters,
  houseAverage,
  meterHistory,
  meterItem,
  readingItem,
  readingPeriods,
  recognizedValues,
  residencyForHouse,
  submitReading,
} from "./state";

type Schemas = components["schemas"];

const NOT_VERIFIED = "Подтвердите квартиру, чтобы работать со счетчиками";

const ZONES_BY_COUNT: Record<number, Schemas["TariffZone"][]> = {
  1: ["single"],
  2: ["day", "night"],
};

const isReply = (value: unknown): value is Reply =>
  typeof value === "object" && value !== null && "status" in value;

// доступ к счётчикам даёт подтверждённая квартира: непопадание сюда - это
// отказ бэка, а не пустой ответ
const flatAccess = (rawFlatId: string) => {
  const flat = findFlat(Number(rawFlatId));

  if (!flat) {
    return notFound("Квартира не найдена");
  }

  const residency = residencyForHouse(flat.house_id);

  if (!residency?.verified) {
    return forbidden(NOT_VERIFIED);
  }

  return flat;
};

const meterAccess = (rawMeterId: string) => {
  const meter = findMeter(Number(rawMeterId));

  if (!meter) {
    return notFound("Счетчик не найден");
  }

  const flat = flatAccess(String(meter.flat_id));

  return isReply(flat) ? flat : meter;
};

export const metersConfigs = [
  {
    path: "/flats/:flat_id/meters" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const flat = flatAccess(request.params.flat_id);

        return isReply(flat) ? flat : ok(flatMeters(flat.id).map(meterItem));
      }),
    ],
  },
  {
    path: "/flats/:flat_id/reading-periods" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const flat = flatAccess(request.params.flat_id);

        return isReply(flat) ? flat : ok(readingPeriods(flat.id));
      }),
    ],
  },
  {
    path: "/meters/:meter_id/readings" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const meter = meterAccess(request.params.meter_id);

        return isReply(meter) ? meter : ok(meterHistory(meter));
      }),
    ],
  },
  {
    path: "/meters/:meter_id/readings" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const meter = meterAccess(request.params.meter_id);

        if (isReply(meter)) {
          return meter;
        }

        const body = request.body as Schemas["SubmitReadingRequest"];
        const zones = ZONES_BY_COUNT[meter.tariff_zones] ?? [];
        const sent = Object.keys(body.values ?? {});

        if (
          sent.length !== zones.length ||
          !zones.every((zone) => sent.includes(zone))
        ) {
          return badRequest(
            "Показания не соответствуют тарифным зонам счетчика",
          );
        }

        if ((body.photos ?? []).length === 0) {
          return badRequest("Приложите фото показаний");
        }

        if (body.period !== currentPeriod()) {
          return conflict("Показания подаются за текущий период");
        }

        const reading = readingItem(submitReading(meter, body), meter);
        const spent = Object.values(reading.consumption).reduce(
          (sum, value) => sum + value,
          0,
        );
        const average = houseAverage(meter);

        return ok({
          reading,
          house_average: average,
          warning: reading.is_below_previous
            ? "Новое значение меньше предыдущего, уточните показание"
            : null,
          // бэк ищет скачок по медиане истории счётчика, моку хватает
          // двукратного превышения соседей
          suggested_category: spent >= average * 2 ? "leak" : null,
        } satisfies Schemas["SubmitReadingResponse"]);
      }),
    ],
  },
  {
    path: "/meters/readings/recognize" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const body = request.body as Schemas["RecognizeReadingRequest"];

        return ok({
          values: recognizedValues(body.meter_type),
        } satisfies Schemas["RecognizeReadingResponse"]);
      }),
    ],
  },
];
