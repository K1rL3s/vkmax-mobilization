import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  endpoint,
  forbidden,
  isReply,
  notFound,
  ok,
} from "./reply";
import {
  HOUSE_AVERAGE,
  findFlat,
  findMeter,
  flatMeters,
  meterHistory,
  meterItem,
  period,
  readingPeriods,
  recognizedValues,
  residencyForHouse,
  submitReading,
} from "./state";

type Schemas = components["schemas"];

const flatAccess = (flatId: number) => {
  const flat = findFlat(flatId);

  if (!flat) {
    return notFound("Квартира не найдена");
  }

  return residencyForHouse(flat.house_id)?.verified
    ? flat
    : forbidden("Подтвердите квартиру, чтобы работать со счетчиками");
};

const meterAccess = (rawMeterId: string) => {
  const meter = findMeter(Number(rawMeterId));

  if (!meter) {
    return notFound("Счетчик не найден");
  }

  const flat = flatAccess(meter.flat_id);

  return isReply(flat) ? flat : meter;
};

export const metersConfigs = [
  endpoint("get", "/flats/:flat_id/meters", (request) => {
    const flat = flatAccess(Number(request.params.flat_id));

    return isReply(flat) ? flat : ok(flatMeters(flat.id).map(meterItem));
  }),
  endpoint("get", "/flats/:flat_id/reading-periods", (request) => {
    const flat = flatAccess(Number(request.params.flat_id));

    return isReply(flat) ? flat : ok(readingPeriods(flat.id));
  }),
  endpoint("get", "/meters/:meter_id/readings", (request) => {
    const meter = meterAccess(request.params.meter_id);

    return isReply(meter) ? meter : ok(meterHistory(meter));
  }),
  endpoint("post", "/meters/:meter_id/readings", (request) => {
    const meter = meterAccess(request.params.meter_id);

    if (isReply(meter)) {
      return meter;
    }

    const body = request.body as Schemas["SubmitReadingRequest"];
    const zones = meter.tariff_zones === 2 ? ["day", "night"] : ["single"];
    const sent = Object.keys(body.values ?? {});

    if (
      sent.length !== zones.length ||
      !zones.every((zone) => sent.includes(zone))
    ) {
      return badRequest("Показания не соответствуют тарифным зонам счетчика");
    }

    if ((body.photos ?? []).length === 0) {
      return badRequest("Приложите фото показаний");
    }

    if (body.period !== period(0)) {
      return conflict("Показания подаются за текущий период");
    }

    const reading = submitReading(meter, body);
    const spent = Object.values(reading.consumption).reduce(
      (sum, value) => sum + value,
      0,
    );
    const average = HOUSE_AVERAGE[meter.type];

    return ok({
      reading,
      house_average: average,
      warning: reading.is_below_previous
        ? "Новое значение меньше предыдущего, уточните показание"
        : null,
      suggested_category: spent >= average * 2 ? "leak" : null,
    } satisfies Schemas["SubmitReadingResponse"]);
  }),
  endpoint("post", "/meters/readings/recognize", (request) =>
    ok({
      values: recognizedValues(
        (request.body as Schemas["RecognizeReadingRequest"]).meter_type,
      ),
    } satisfies Schemas["RecognizeReadingResponse"]),
  ),
];
