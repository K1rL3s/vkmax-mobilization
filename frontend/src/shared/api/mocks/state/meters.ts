import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

import { fileUrl } from "./files";
import { period, today } from "./time";

export type MockMeter = {
  id: number;
  flat_id: number;
  type: Schemas["MeterType"];
  tariff_zones: number;
  serial: string;
  next_verification_date: string | null;
};

export type MockReading = {
  id: number;
  meter_id: number;
  period: string;
  values: Record<string, number>;
  photos: string[];
  ocr_used: boolean;
  submitted_at: string;
};

export const METERS: MockMeter[] = [
  {
    id: 201,
    flat_id: 101,
    type: "electricity",
    tariff_zones: 2,
    serial: "E-88214",
    next_verification_date: "2029-04-01",
  },
  {
    id: 202,
    flat_id: 101,
    type: "cold_water",
    tariff_zones: 1,
    serial: "CW-10432",
    next_verification_date: "2027-11-01",
  },
  {
    id: 203,
    flat_id: 101,
    type: "hot_water",
    tariff_zones: 1,
    serial: "HW-22881",
    next_verification_date: "2027-11-01",
  },
];

// показания прошлого месяца: с ними у формы есть «прошлое значение», а у
// отправленного показания - расход
export const SEED_READINGS: MockReading[] = [
  {
    id: 3001,
    meter_id: 201,
    period: period(1),
    values: { day: 12310000, night: 4150000 },
    photos: [],
    ocr_used: false,
    submitted_at: period(1),
  },
  {
    id: 3002,
    meter_id: 202,
    period: period(1),
    values: { single: 214300 },
    photos: [],
    ocr_used: false,
    submitted_at: period(1),
  },
  {
    id: 3003,
    meter_id: 203,
    period: period(1),
    values: { single: 118900 },
    photos: [],
    ocr_used: false,
    submitted_at: period(1),
  },
];

// тариф в 1/10000 рубля за единицу, как в справочнике тарифов бэка
const METER_TARIFF: Record<Schemas["MeterType"], number> = {
  electricity: 56000,
  cold_water: 350000,
  hot_water: 2100000,
  gas: 78000,
  heating: 21000000,
};

// среднее по дому считать не из чего: в моке счётчики есть только у одной
// квартиры, поэтому расход соседей задан демо-значением
const HOUSE_AVERAGE: Record<Schemas["MeterType"], number> = {
  electricity: 210000,
  cold_water: 4200,
  hot_water: 3100,
  gas: 5400,
  heating: 140,
};

// сколько прибавляет к прошлому показанию «распознавание» фото
const OCR_STEP: Record<Schemas["MeterType"], number> = {
  electricity: 148000,
  cold_water: 4300,
  hot_water: 3400,
  gas: 5200,
  heating: 120,
};

const state = {
  readings: [...SEED_READINGS],
  nextReadingId: 3100,
};

export const resetMeters = (): void => {
  state.readings = [...SEED_READINGS];
  state.nextReadingId = 3100;
};

export const currentPeriod = (): string => period(0);

export const flatMeters = (flatId: number): MockMeter[] =>
  METERS.filter((meter) => meter.flat_id === flatId);

export const findMeter = (meterId: number): MockMeter | undefined =>
  METERS.find((meter) => meter.id === meterId);

const meterReadings = (meterId: number): MockReading[] =>
  state.readings
    .filter((reading) => reading.meter_id === meterId)
    .sort(
      (a, b) =>
        b.period.localeCompare(a.period) ||
        b.submitted_at.localeCompare(a.submitted_at),
    );

export const meterItem = (meter: MockMeter): Schemas["MeterItem"] => {
  const last = meterReadings(meter.id).at(0);
  const expired =
    meter.next_verification_date !== null &&
    meter.next_verification_date < today();

  return {
    id: meter.id,
    flat_id: meter.flat_id,
    type: meter.type,
    tariff_zones: meter.tariff_zones,
    serial: meter.serial,
    can_submit: !expired,
    verification_expired: expired,
    next_verification_date: meter.next_verification_date,
    last_period: last?.period ?? null,
    last_values: last?.values ?? null,
  };
};

export const readingPeriods = (
  flatId: number,
): Schemas["ReadingPeriodItem"][] => {
  const current = currentPeriod();

  return [
    {
      period: current,
      is_open: true,
      is_submitted: flatMeters(flatId).some((meter) =>
        meterReadings(meter.id).some((reading) => reading.period === current),
      ),
    },
  ];
};

const previousValues = (
  meterId: number,
  before: string,
): Record<string, number> | null =>
  meterReadings(meterId).find((reading) => reading.period < before)?.values ??
  null;

const consumptionOf = (
  values: Record<string, number>,
  previous: Record<string, number> | null,
): Record<string, number> =>
  Object.fromEntries(
    Object.entries(values).map(([zone, value]) => [
      zone,
      // первая подача расхода не даёт: считать его от нуля значит выставить
      // жителю весь ресурс, прошедший через счётчик за всю его жизнь
      previous === null ? 0 : value - (previous[zone] ?? value),
    ]),
  );

// тысячные объёма * тариф (1/10000 рубля) даёт 1/100000 копейки
const kopecks = (consumption: Record<string, number>, tariff: number): number =>
  Math.floor(
    (Object.values(consumption).reduce(
      (sum, value) => sum + value * tariff,
      0,
    ) +
      50000) /
      100000,
  );

export const readingItem = (
  reading: MockReading,
  meter: MockMeter,
): Schemas["ReadingItem"] => {
  const previous = previousValues(meter.id, reading.period);
  const consumption = consumptionOf(reading.values, previous);

  return {
    id: reading.id,
    meter_id: reading.meter_id,
    period: reading.period,
    values: reading.values,
    consumption,
    photos: reading.photos.map((name) => ({
      name,
      url: fileUrl(name),
    })),
    is_below_previous:
      previous !== null &&
      Object.entries(reading.values).some(
        ([zone, value]) => value < (previous[zone] ?? value),
      ),
    ocr_used: reading.ocr_used,
    submitted_at: reading.submitted_at,
    amount: kopecks(consumption, METER_TARIFF[meter.type]),
  };
};

export const meterHistory = (meter: MockMeter): Schemas["ReadingItem"][] =>
  meterReadings(meter.id).map((reading) => readingItem(reading, meter));

export const submitReading = (
  meter: MockMeter,
  body: Schemas["SubmitReadingRequest"],
): MockReading => {
  const created: MockReading = {
    id: state.nextReadingId,
    meter_id: meter.id,
    period: body.period,
    values: body.values,
    photos: body.photos ?? [],
    ocr_used: body.ocr_used,
    submitted_at: new Date().toISOString(),
  };

  state.nextReadingId += 1;
  state.readings = [created, ...state.readings];

  return created;
};

export const houseAverage = (meter: MockMeter): number =>
  HOUSE_AVERAGE[meter.type];

export const recognizedValues = (
  meterType: Schemas["MeterType"],
): Record<string, number> | null => {
  const meter = METERS.find((item) => item.type === meterType);

  if (!meter) {
    return null;
  }

  const last = meterReadings(meter.id).at(0);

  if (!last) {
    return null;
  }

  const step = OCR_STEP[meterType];

  return Object.fromEntries(
    Object.entries(last.values).map(([zone, value]) => [
      zone,
      // ночью в квартире тратят меньше, чем днём - демо-прирост это повторяет
      value + (zone === "night" ? Math.round(step / 3000) * 1000 : step),
    ]),
  );
};
