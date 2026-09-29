import type { components } from "../../schema/generated";

import { fileUrl } from "./files";
import { period, today } from "./time";

type Schemas = components["schemas"];

export type MockMeter = {
  id: number;
  flat_id: number;
  type: Schemas["MeterType"];
  tariff_zones: number;
  serial: string;
  next_verification_date: string | null;
};

type MockReading = {
  id: number;
  meter_id: number;
  period: string;
  values: Record<string, number>;
  photos: string[];
  ocr_used: boolean;
  submitted_at: string;
};

const METERS: MockMeter[] = [
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

const seedReading = (
  id: number,
  meter_id: number,
  values: Record<string, number>,
): MockReading => ({
  id,
  meter_id,
  period: period(1),
  values,
  photos: [],
  ocr_used: false,
  submitted_at: period(1),
});

const readings: MockReading[] = [
  seedReading(3001, 201, { day: 12310000, night: 4150000 }),
  seedReading(3002, 202, { single: 214300 }),
  seedReading(3003, 203, { single: 118900 }),
];

let nextReadingId = 3100;

const METER_TARIFF: Record<Schemas["MeterType"], number> = {
  electricity: 56000,
  cold_water: 350000,
  hot_water: 2100000,
  gas: 78000,
  heating: 21000000,
};

export const HOUSE_AVERAGE: Record<Schemas["MeterType"], number> = {
  electricity: 210000,
  cold_water: 4200,
  hot_water: 3100,
  gas: 5400,
  heating: 140,
};

const OCR_STEP: Record<Schemas["MeterType"], number> = {
  electricity: 148000,
  cold_water: 4300,
  hot_water: 3400,
  gas: 5200,
  heating: 120,
};

export const flatMeters = (flatId: number): MockMeter[] =>
  METERS.filter((meter) => meter.flat_id === flatId);

export const findMeter = (meterId: number): MockMeter | undefined =>
  METERS.find((meter) => meter.id === meterId);

const meterReadings = (meterId: number): MockReading[] =>
  readings
    .filter((reading) => reading.meter_id === meterId)
    .sort(
      (a, b) =>
        b.period.localeCompare(a.period) ||
        b.submitted_at.localeCompare(a.submitted_at),
    );

export const meterItem = (meter: MockMeter): Schemas["MeterItem"] => {
  const last = meterReadings(meter.id).at(0);
  const prior = meterReadings(meter.id).find(
    (reading) => last !== undefined && reading.period < last.period,
  );
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
    prior_period: prior?.period ?? null,
    prior_values: prior?.values ?? null,
  };
};

export const readingPeriods = (
  flatId: number,
): Schemas["ReadingPeriodItem"][] => {
  const current = period(0);

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

const readingItem = (
  reading: MockReading,
  meter: MockMeter,
): Schemas["ReadingItem"] => {
  const previous =
    meterReadings(meter.id).find((item) => item.period < reading.period)
      ?.values ?? null;
  const consumption = Object.fromEntries(
    Object.entries(reading.values).map(([zone, value]) => [
      zone,
      previous === null ? 0 : value - (previous[zone] ?? value),
    ]),
  );

  return {
    id: reading.id,
    meter_id: reading.meter_id,
    period: reading.period,
    values: reading.values,
    consumption,
    photos: reading.photos.map((name) => ({
      name,
      url: fileUrl(name),
      is_video: false,
    })),
    is_below_previous:
      previous !== null &&
      Object.entries(reading.values).some(
        ([zone, value]) => value < (previous[zone] ?? value),
      ),
    ocr_used: reading.ocr_used,
    submitted_at: reading.submitted_at,
    amount: Math.floor(
      (Object.values(consumption).reduce(
        (sum, value) => sum + value * METER_TARIFF[meter.type],
        0,
      ) +
        50000) /
        100000,
    ),
  };
};

export const meterHistory = (meter: MockMeter): Schemas["ReadingItem"][] =>
  meterReadings(meter.id).map((reading) => readingItem(reading, meter));

export const submitReading = (
  meter: MockMeter,
  body: Schemas["SubmitReadingRequest"],
): Schemas["ReadingItem"] => {
  const created: MockReading = {
    id: nextReadingId++,
    meter_id: meter.id,
    period: body.period,
    values: body.values,
    photos: body.photos ?? [],
    ocr_used: body.ocr_used,
    submitted_at: new Date().toISOString(),
  };
  readings.unshift(created);

  return readingItem(created, meter);
};

export const recognizedValues = (
  meterType: Schemas["MeterType"],
): Record<string, number> | null => {
  const meter = METERS.find((item) => item.type === meterType);
  const last = meter && meterReadings(meter.id).at(0);

  if (!last) {
    return null;
  }

  const step = OCR_STEP[meterType];

  return Object.fromEntries(
    Object.entries(last.values).map(([zone, value]) => [
      zone,
      value + (zone === "night" ? Math.round(step / 3000) * 1000 : step),
    ]),
  );
};
