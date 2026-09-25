import type { components } from "@/shared/api/schema/generated";

type ChartSeries = components["schemas"]["ChartSeries"];

const MONTHS = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

// подписи точек недельного графика - ISO-даты понедельников; дата разбирается
// строкой, потому что `new Date("2026-09-15")` это полночь UTC и в минусовом
// поясе съезжает на сутки назад
export const weekTick = (iso: string): string => {
  const [, month, day] = iso.split("-");

  return `${day}.${month}`;
};

export const weekTitle = (iso: string): string => {
  const [year, month, day] = iso.split("-");

  return `Неделя с ${Number(day)} ${MONTHS[Number(month) - 1]} ${year}`;
};

// нулевая категория в столбцах - пустая строка с подписью, место она занимает
// зря; в разрезе по каналу ноль наоборот показывается, там это результат
export const chartPoints = (series: ChartSeries) =>
  series.key === "by_category"
    ? series.points.filter((point) => point.value > 0)
    : series.points;
