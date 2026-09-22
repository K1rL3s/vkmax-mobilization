import type { components } from "../schema/generated";

import { badRequest, notFound, ok, route } from "./reply";
import { findHouse, residencyForHouse } from "./state";

type Schemas = components["schemas"];

const CATEGORIES = new Set<string>(["requests", "announcements", "meters"]);

const LEVELS = new Set<string>(["sound", "silent", "off"]);

// бэк без сохранённого выбора отвечает «без звука»
const levels: Record<
  Schemas["NotificationCategory"],
  Schemas["NotificationLevel"]
> = { requests: "silent", announcements: "silent", meters: "silent" };

const settings = (): Schemas["NotificationSettingsResponse"] => ({
  settings: Object.entries(levels).map(([category, level]) => ({
    category: category as Schemas["NotificationCategory"],
    level,
  })),
});

// история тарифов, как её отдаёт бэк: свежие сверху, действует последний
// наступивший по каждой услуге
const TARIFFS: Schemas["TariffItem"][] = [
  {
    id: 6,
    service: "cold_water",
    label: "Холодная вода",
    value: 384000,
    unit: "м³",
    valid_from: "2026-07-01",
    document: null,
  },
  {
    id: 7,
    service: "hot_water",
    label: "Горячая вода",
    value: 2125000,
    unit: "м³",
    valid_from: "2026-07-01",
    document: null,
  },
  {
    id: 8,
    service: "electricity",
    label: "Электроэнергия",
    value: 56200,
    unit: "кВт·ч",
    valid_from: "2026-07-01",
    document: null,
  },
  {
    id: 1,
    service: "cold_water",
    label: "Холодная вода",
    value: 351000,
    unit: "м³",
    valid_from: "2025-07-01",
    document: null,
  },
  {
    id: 2,
    service: "hot_water",
    label: "Горячая вода",
    value: 1980000,
    unit: "м³",
    valid_from: "2025-07-01",
    document: null,
  },
  {
    id: 3,
    service: "electricity",
    label: "Электроэнергия",
    value: 52100,
    unit: "кВт·ч",
    valid_from: "2025-07-01",
    document: null,
  },
  {
    id: 4,
    service: "heating",
    label: "Отопление",
    value: 24500000,
    unit: "Гкал",
    valid_from: "2025-07-01",
    document: null,
  },
  {
    id: 5,
    service: "maintenance",
    label: "Содержание жилья",
    value: 289000,
    unit: "м²",
    valid_from: "2025-07-01",
    document: null,
  },
];

export const notificationsConfigs = [
  {
    path: "/me/notifications" as const,
    method: "get" as const,
    routes: [route(() => ok(settings()))],
  },
  {
    path: "/me/notifications" as const,
    method: "put" as const,
    routes: [
      route((request) => {
        const items = request.body.settings;

        if (
          !Array.isArray(items) ||
          !items.every(
            (item: { category?: unknown; level?: unknown }) =>
              CATEGORIES.has(String(item.category)) &&
              LEVELS.has(String(item.level)),
          )
        ) {
          return badRequest("Неизвестная категория или уровень уведомлений");
        }

        for (const item of items as Schemas["NotificationSettingItem"][]) {
          levels[item.category] = item.level;
        }

        return ok(settings());
      }),
    ],
  },
  {
    path: "/houses/:house_id/tariffs" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const house = findHouse(Number(request.params.house_id));

        if (!house || !residencyForHouse(house.id)) {
          return notFound("Дом не найден");
        }

        // тарифы публикует УК из кабинета, у неподключённого дома их нет
        return ok(house.is_connected ? TARIFFS : []);
      }),
    ],
  },
];
