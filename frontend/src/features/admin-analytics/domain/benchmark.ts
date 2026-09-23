import type { components } from "@/shared/api/schema/generated";
import type { StatusPillTone } from "@/shared/ui/status-pill";

type BenchmarkRegionRow = components["schemas"]["BenchmarkRegionRow"];

// верхняя треть рейтинга - повод похвалить, остальное просто место
export const rankTone = (rank: number, total: number): StatusPillTone =>
  rank <= Math.ceil(total / 3) ? "positive" : "neutral";

// в `regions[]` сначала строки регионов (`city: null`), потом городов;
// вложенности город-в-регион нет, это два плоских списка
export const splitRegions = (rows: BenchmarkRegionRow[]) => ({
  regions: rows.filter((row) => row.city === null || row.city === undefined),
  cities: rows.filter((row) => row.city !== null && row.city !== undefined),
});
