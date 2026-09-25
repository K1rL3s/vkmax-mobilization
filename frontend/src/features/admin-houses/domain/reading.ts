import { formatReading, METER_UNIT, ZONE_LABEL } from "@/features/meters";
import type { components } from "@/shared/api/schema/generated";

export type Reading = components["schemas"]["AdminReadingItem"];

const ZONE_ORDER = ["single", "day", "night"];

const byZone = (values: Record<string, number>, sign: boolean) =>
  Object.entries(values)
    .sort(([a], [b]) => ZONE_ORDER.indexOf(a) - ZONE_ORDER.indexOf(b))
    .map(([zone, value]) => {
      const number =
        sign && value > 0 ? `+${formatReading(value)}` : formatReading(value);

      return zone === "day" || zone === "night"
        ? `${ZONE_LABEL[zone].toLowerCase()} ${number}`
        : number;
    })
    .join(" · ");

export const readingValue = (reading: Reading) =>
  `${byZone(reading.values, false)} ${METER_UNIT[reading.meter_type]}`;

export const readingConsumption = (reading: Reading) =>
  `расход ${byZone(reading.consumption, true)}`;
