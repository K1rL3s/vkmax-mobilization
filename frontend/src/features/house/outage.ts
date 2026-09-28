import type { components } from "@/shared/api/schema/generated";
import { formatDayTime } from "@/shared/lib/format";

export type Outage = components["schemas"]["OutageItem"];
type RequestCategory = components["schemas"]["RequestCategory"];

const RESOURCE_LABEL: Record<Outage["resource"], string> = {
  cold_water: "холодной воды",
  hot_water: "горячей воды",
  electricity: "электричества",
  gas: "газа",
  heating: "отопления",
  maintenance: "услуги",
  overhaul: "услуги",
  waste: "вывоза мусора",
  penalty: "услуги",
  recalculation: "услуги",
};

const CATEGORY_RESOURCES: Partial<
  Record<RequestCategory, Outage["resource"][]>
> = {
  water_supply: ["cold_water", "hot_water"],
  heating: ["heating"],
  electricity: ["electricity"],
};

export const outageTitle = (outage: Outage) =>
  `Отключение ${RESOURCE_LABEL[outage.resource]} до ${formatDayTime(outage.ends_at)}`;

export const outageForCategory = (
  outages: Outage[],
  category: RequestCategory | null,
): Outage | undefined => {
  const resources = category ? CATEGORY_RESOURCES[category] : undefined;
  const now = Date.now();

  return outages.find(
    (outage) =>
      resources?.includes(outage.resource) &&
      Date.parse(outage.starts_at) <= now,
  );
};
