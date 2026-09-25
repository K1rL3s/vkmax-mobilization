import type { components } from "../schema/generated";

import { badRequest, conflict, ok, route } from "./reply";

type Schemas = components["schemas"];

const day = 24 * 60 * 60 * 1000;

const date = (offsetDays: number): string =>
  new Date(Date.now() + offsetDays * day).toISOString().slice(0, 10);

// 12 понедельников подряд, как их считает бэк: последний - понедельник этой
// недели
const mondays = (): string[] => {
  const today = new Date();
  const thisMonday = new Date(
    today.getTime() - ((today.getUTCDay() + 6) % 7) * day,
  );

  return Array.from({ length: 12 }, (_, index) =>
    new Date(thisMonday.getTime() - (11 - index) * 7 * day)
      .toISOString()
      .slice(0, 10),
  );
};

const WEEK_COUNTS = [18, 22, 19, 27, 31, 24, 29, 35, 28, 33, 41, 37];

// чип отдаёт дату начала периода, длину бэк считает от неё
const periodDays = (from: string | undefined): 30 | 90 =>
  from !== undefined && Math.round((Date.now() - Date.parse(from)) / day) >= 60
    ? 90
    : 30;

const dashboard = (days: number): Schemas["DashboardResponse"] => {
  const scale = days === 90 ? 3 : 1;

  return {
    period_from: date(-days),
    period_to: date(0),
    tiles: [
      { key: "active", label: "Активные заявки", unit: "count", value: 47 },
      { key: "overdue", label: "Просрочено", unit: "count", value: 6 },
      {
        key: "accept_time",
        label: "Среднее время до принятия",
        unit: "minutes",
        value: days === 90 ? 3145 : 260,
      },
      {
        key: "repeat_share",
        label: "Доля повторных",
        unit: "percent",
        value: days === 90 ? 64 : 1180,
      },
    ],
    charts: [
      {
        key: "by_category",
        title: "Заявки по категориям",
        unit: "count",
        points: [
          { label: "Сантехника", value: 64 * scale },
          { label: "Электрика", value: 41 * scale },
          { label: "Лифт", value: 23 * scale },
          { label: "Уборка подъезда", value: 17 * scale },
          { label: "Отопление", value: 9 * scale },
          { label: "Домофон", value: 0 },
          { label: "Кровля", value: 0 },
        ],
      },
      {
        key: "by_week",
        title: "Динамика по неделям",
        unit: "count",
        points: mondays().map((label, index) => ({
          label,
          value: WEEK_COUNTS[index] ?? 0,
        })),
      },
    ],
    is_empty: false,
  };
};

// текущий период показаний и окно подачи: окно открыто, чтобы кнопка
// напоминания была живой без правки файла
const period = (): string => `${new Date().toISOString().slice(0, 7)}-01`;

const houses: Schemas["MetersSeasonHouse"][] = [
  {
    house_id: 1,
    address: "Казань, ул. Баумана, д. 12",
    flats_total: 120,
    submitted: 94,
    not_submitted: 26,
    percent: 7833,
  },
  {
    house_id: 2,
    address: "Казань, ул. Баумана, д. 14",
    flats_total: 64,
    submitted: 31,
    not_submitted: 33,
    percent: 4844,
  },
  {
    // дом без единого сданного показания: ноль тоже читается как результат
    house_id: 3,
    address:
      "Республика Татарстан, Казань, ул. Академика Арбузова, д. 16, корпус 2",
    flats_total: 48,
    submitted: 0,
    not_submitted: 48,
    percent: 0,
  },
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

// все четыре канала всегда, включая нулевой: ноль это тоже результат, а не
// повод спрятать строку
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

// порядок по имени, как отдаёт бэк; у последнего ничего не закрыто - нули и
// null, чтобы прочерк в таблице был виден без правки файла
const EXECUTORS: Schemas["ExecutorStatsItem"][] = [
  {
    user_id: 501,
    name: "Абдрахманов Ильдар Рустемович",
    closed: 38,
    repeat_share: 790,
    median_time: 214,
    rating: 468,
  },
  {
    user_id: 502,
    name: "Волкова Анна",
    closed: 52,
    repeat_share: 1540,
    median_time: 96,
    rating: 412,
  },
  {
    user_id: 503,
    name: "Гараев Тимур",
    closed: 17,
    repeat_share: 30,
    median_time: 3180,
    rating: 500,
  },
  {
    user_id: 504,
    name: "Сафин Рустам",
    closed: 0,
    repeat_share: 0,
    median_time: null,
    rating: null,
  },
];

// у «доли повторных» ранга нет, и метрика без ранга выпадает из сравнения
// целиком: значение остаётся, сравнение заменяется объяснением
const BENCHMARK_METRICS: Schemas["BenchmarkMetric"][] = [
  {
    key: "accept_time",
    label: "Среднее время до принятия",
    unit: "minutes",
    value: 260,
    platform_median: 412,
    rank: 4,
    total: 37,
  },
  {
    key: "close_time",
    label: "Среднее время до закрытия",
    unit: "minutes",
    value: 2840,
    platform_median: 2210,
    rank: 24,
    total: 37,
  },
  {
    key: "overdue_share",
    label: "Доля просроченных",
    unit: "percent",
    value: 1270,
    platform_median: 980,
    rank: 26,
    total: 37,
  },
  {
    key: "rating",
    label: "Средняя оценка",
    unit: "points",
    value: 452,
    platform_median: 430,
    rank: 11,
    total: 37,
  },
  {
    key: "digital_share",
    label: "Доля цифровых обращений",
    unit: "percent",
    value: 10000,
    platform_median: 7400,
    rank: 1,
    total: 37,
  },
  {
    key: "repeat_share",
    label: "Доля повторных",
    unit: "percent",
    value: 1180,
    platform_median: null,
    rank: null,
    total: null,
  },
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

// тринадцать домов: кнопка «Показать все ещё 3» появляется сама
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

// напоминание дедуплицируется по человеку и календарному дню: второй раз за
// сутки бэк вернёт ноль, а не откажет
let remindedOn: string | null = null;

export const adminAnalyticsConfigs = [
  {
    path: "/admin/analytics/dashboard" as const,
    method: "get" as const,
    routes: [
      route((request) => ok(dashboard(periodDays(request.query.date_from)))),
    ],
  },
  {
    path: "/admin/analytics/meters-season" as const,
    method: "get" as const,
    routes: [route(() => ok(metersSeason()))],
  },
  {
    path: "/admin/analytics/meters-season/remind" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const season = metersSeason();
        const asked = request.body.period;

        if (typeof asked === "string" && asked !== season.period) {
          return badRequest("Напомнить можно только по текущему периоду");
        }

        if (!season.window_open) {
          return conflict("Приём показаний закрыт");
        }

        const today = new Date().toISOString().slice(0, 10);
        const queued = remindedOn === today ? 0 : season.not_submitted;
        remindedOn = today;

        return ok({ queued } satisfies Schemas["RemindNotSubmittedResponse"]);
      }),
    ],
  },
  {
    path: "/admin/analytics/channels" as const,
    method: "get" as const,
    routes: [
      route((request) =>
        ok(channels(periodDays(request.query.date_from) === 90 ? 3 : 1)),
      ),
    ],
  },
  {
    path: "/admin/analytics/executors" as const,
    method: "get" as const,
    routes: [
      route((request) =>
        ok(
          periodDays(request.query.date_from) === 90
            ? EXECUTORS.map((item) => ({ ...item, closed: item.closed * 3 }))
            : EXECUTORS,
        ),
      ),
    ],
  },
  {
    path: "/admin/analytics/benchmark" as const,
    method: "get" as const,
    routes: [
      route(() =>
        ok({
          metrics: BENCHMARK_METRICS,
          regions: BENCHMARK_REGIONS,
          unconnected_houses: UNCONNECTED,
          is_empty: false,
        } satisfies Schemas["BenchmarkResponse"]),
      ),
    ],
  },
];
