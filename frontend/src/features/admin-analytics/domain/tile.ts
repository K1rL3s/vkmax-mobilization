import type { components } from "@/shared/api/schema/generated";

import { formatMetric } from "./metric";

type DashboardTile = components["schemas"]["DashboardTile"];

export type TileView = {
  key: string;
  label: string;
  value: string;
  note: string | null;
  isAlert: boolean;
};

// «сейчас» - состояние на текущий момент, период его не касается; всё
// остальное, включая незнакомый ключ, читается как число за период
const isNow = (tile: DashboardTile) =>
  tile.key === "active" || tile.key === "overdue";

export const splitTiles = (tiles: DashboardTile[]) => ({
  now: tiles.filter(isNow),
  period: tiles.filter((tile) => !isNow(tile)),
});

export const tileView = (tile: DashboardTile): TileView => {
  // ноль часов среднего времени врёт: принятых заявок просто не было
  if (tile.key === "accept_time" && tile.value === 0) {
    return {
      key: tile.key,
      label: tile.label,
      value: "—",
      note: "за период нет принятых заявок",
      isAlert: false,
    };
  }

  return {
    key: tile.key,
    label: tile.label,
    value: formatMetric(tile.value, tile.unit),
    note: null,
    isAlert: tile.key === "overdue" && tile.value > 0,
  };
};
