import type { components } from "../schema/generated";

import { badRequest, endpoint, ok } from "./reply";
import { DAY, days, today } from "./state";

type Schemas = components["schemas"];

const mondays = (): string[] => {
  const now = new Date();
  const thisMonday = new Date(
    now.getTime() - ((now.getUTCDay() + 6) % 7) * DAY,
  );

  return Array.from({ length: 12 }, (_, index) =>
    new Date(thisMonday.getTime() - (11 - index) * 7 * DAY)
      .toISOString()
      .slice(0, 10),
  );
};

const WEEK_COUNTS = [18, 22, 19, 27, 31, 24, 29, 35, 28, 33, 41, 37];

const periodDays = (from: string | undefined): 30 | 90 =>
  from !== undefined && Math.round((Date.now() - Date.parse(from)) / DAY) >= 60
    ? 90
    : 30;

const dashboard = (span: number): Schemas["DashboardResponse"] => {
  const scale = span === 90 ? 3 : 1;

  return {
    period_from: days(-span).slice(0, 10),
    period_to: days(0).slice(0, 10),
    tiles: [
      { key: "active", label: "Активные заявки", unit: "count", value: 47 },
      { key: "overdue", label: "Просрочено", unit: "count", value: 6 },
      {
        key: "accept_time",
        label: "Среднее время до принятия",
        unit: "minutes",
        value: span === 90 ? 3145 : 260,
      },
      {
        key: "repeat_share",
        label: "Доля повторных",
        unit: "percent",
        value: span === 90 ? 64 : 1180,
      },
    ],
    charts: [
      {
        key: "by_category",
        title: "Заявки по категориям",
        unit: "count",
        points: [
          { label: "Протечка", value: 64 * scale },
          { label: "Электричество", value: 41 * scale },
          { label: "Лифт", value: 23 * scale },
          { label: "Подъезд", value: 17 * scale },
          { label: "Отопление", value: 9 * scale },
          { label: "Мусор", value: 0 },
          { label: "Двор и территория", value: 0 },
        ],
      },
      {
        key: "by_week",
        title: "Динамика по неделям",
        unit: "count",
        points: mondays().map((label, index) => ({
          label,
          value: WEEK_COUNTS[index],
        })),
      },
    ],
    is_empty: false,
  };
};

const period = (): string => `${new Date().toISOString().slice(0, 7)}-01`;

const seasonHouse = (
  house_id: number,
  address: string,
  flats_total: number,
  submitted: number,
  percent: number,
): Schemas["MetersSeasonHouse"] => ({
  house_id,
  address,
  flats_total,
  submitted,
  not_submitted: flats_total - submitted,
  percent,
});

const houses = [
  seasonHouse(1, "Казань, ул. Баумана, д. 12", 120, 94, 7833),
  seasonHouse(2, "Казань, ул. Баумана, д. 14", 64, 31, 4844),
  seasonHouse(
    3,
    "Республика Татарстан, Казань, ул. Академика Арбузова, д. 16, корпус 2",
    48,
    0,
    0,
  ),
];

const metersSeason = (): Schemas["MetersSeasonResponse"] => ({
  period: period(),
  window_from: `${period().slice(0, 8)}20`,
  window_to: `${period().slice(0, 8)}25`,
  window_open: true,
  submitted: houses.reduce((sum, house) => sum + house.submitted, 0),
  not_submitted: houses.reduce((sum, house) => sum + house.not_submitted, 0),
  houses,
  is_empty: false,
});

const CHANNEL_SHARE: [Schemas["RequestChannel"], number][] = [
  ["miniapp", 61],
  ["bot", 24],
  ["chat", 15],
  ["phone", 0],
];

const channels = (scale: number): Schemas["ChannelsSplitResponse"] => {
  const items = CHANNEL_SHARE.map(([channel, count]) => ({
    channel,
    count: count * scale,
  }));
  const total = items.reduce((sum, item) => sum + item.count, 0);

  return {
    total,
    items: items.map((item) => ({
      ...item,
      share: Math.round((item.count / total) * 10000),
    })),
    is_empty: false,
  };
};

const executor = (
  user_id: number,
  name: string,
  closed: number,
  repeat_share: number,
  median_time: number | null,
  rating: number | null,
): Schemas["ExecutorStatsItem"] => ({
  user_id,
  name,
  closed,
  repeat_share,
  median_time,
  rating,
});

const EXECUTORS = [
  executor(501, "Абдрахманов Ильдар Рустемович", 38, 790, 214, 468),
  executor(502, "Волкова Анна", 52, 1540, 96, 412),
  executor(503, "Гараев Тимур", 17, 30, 3180, 500),
  executor(504, "Сафин Рустам", 0, 0, null, null),
];

const metric = (
  key: string,
  label: string,
  unit: Schemas["BenchmarkMetric"]["unit"],
  value: number,
  platform_median: number | null,
  rank: number | null,
): Schemas["BenchmarkMetric"] => ({
  key,
  label,
  unit,
  value,
  platform_median,
  rank,
  total: rank === null ? null : 37,
});

const BENCHMARK_METRICS = [
  metric("accept_time", "Среднее время до принятия", "minutes", 260, 412, 4),
  metric("close_time", "Среднее время до закрытия", "minutes", 2840, 2210, 24),
  metric("overdue_share", "Доля просроченных", "percent", 1270, 980, 26),
  metric("rating", "Средняя оценка", "points", 452, 430, 11),
  metric("digital_share", "Доля цифровых обращений", "percent", 10000, 7400, 1),
  metric("repeat_share", "Доля повторных", "percent", 1180, null, null),
];

const BENCHMARK_REGIONS: Schemas["BenchmarkRegionRow"][] = [
  {
    region: "Республика Татарстан",
    orgs_count: 21,
    unit: "minutes",
    value: 385,
  },
  { region: "Самарская область", orgs_count: 11, unit: "minutes", value: 470 },
  { region: "Кировская область", orgs_count: 5, unit: "minutes", value: 612 },
  {
    region: "Республика Татарстан",
    city: "Казань",
    orgs_count: 14,
    unit: "minutes",
    value: 352,
  },
  {
    region: "Республика Татарстан",
    city: "Набережные Челны",
    orgs_count: 7,
    unit: "minutes",
    value: 441,
  },
  {
    region: "Самарская область",
    city: "Самара",
    orgs_count: 8,
    unit: "minutes",
    value: 455,
  },
];

const UNCONNECTED: Schemas["UnconnectedHouseItem"][] = [
  ["Казань, ул. Ленина, д. 4", 38],
  ["Казань, ул. Чистопольская, д. 71", 27],
  ["Казань, ул. Салиха Сайдашева, д. 12", 24],
  ["Казань, просп. Победы, д. 139", 21],
  ["Казань, ул. Академика Глушко, д. 22", 19],
  ["Казань, ул. Фучика, д. 88", 17],
  ["Казань, ул. Рихарда Зорге, д. 66", 14],
  ["Республика Татарстан, Казань, ул. Академика Арбузова, д. 16, корпус 2", 12],
  ["Казань, ул. Беломорская, д. 244", 9],
  ["Казань, ул. Гаврилова, д. 10", 7],
  ["Казань, ул. Хайдара Бигичева, д. 5", 6],
  ["Казань, ул. Мавлютова, д. 34", 4],
  ["Казань, ул. Дубравная, д. 51", 2],
].map(([address, waiting], index) => ({
  house_id: 900 + index,
  address: String(address),
  waiting: Number(waiting),
}));

let remindedOn: string | null = null;

export const adminAnalyticsConfigs = [
  endpoint("get", "/admin/analytics/dashboard", (request) =>
    ok(dashboard(periodDays(request.query.date_from))),
  ),
  endpoint("get", "/admin/analytics/meters-season", () => ok(metersSeason())),
  endpoint("post", "/admin/analytics/meters-season/remind", (request) => {
    const season = metersSeason();
    const asked = request.body.period;

    if (typeof asked === "string" && asked !== season.period) {
      return badRequest("Напомнить можно только по текущему периоду");
    }

    const day = today();
    const queued = remindedOn === day ? 0 : season.not_submitted;
    remindedOn = day;

    return ok({ queued } satisfies Schemas["RemindNotSubmittedResponse"]);
  }),
  endpoint("get", "/admin/analytics/channels", (request) =>
    ok(channels(periodDays(request.query.date_from) === 90 ? 3 : 1)),
  ),
  endpoint("get", "/admin/analytics/executors", (request) =>
    ok(
      periodDays(request.query.date_from) === 90
        ? EXECUTORS.map((item) => ({ ...item, closed: item.closed * 3 }))
        : EXECUTORS,
    ),
  ),
  endpoint("get", "/admin/analytics/benchmark", () =>
    ok({
      metrics: BENCHMARK_METRICS,
      regions: BENCHMARK_REGIONS,
      unconnected_houses: UNCONNECTED,
      is_empty: false,
    } satisfies Schemas["BenchmarkResponse"]),
  ),
];
