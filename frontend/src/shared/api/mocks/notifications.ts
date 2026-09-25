import type { components } from "../schema/generated";

import { badRequest, endpoint, ok } from "./reply";

type Schemas = components["schemas"];

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

export const notificationsConfigs = [
  endpoint("get", "/me/notifications", () => ok(settings())),
  endpoint("put", "/me/notifications", (request) => {
    const items = request.body.settings;

    if (
      !Array.isArray(items) ||
      !items.every(
        (item: { category?: unknown; level?: unknown }) =>
          ["requests", "announcements", "meters"].includes(
            String(item.category),
          ) && ["sound", "silent", "off"].includes(String(item.level)),
      )
    ) {
      return badRequest("Неизвестная категория или уровень уведомлений");
    }

    for (const item of items as Schemas["NotificationSettingItem"][]) {
      levels[item.category] = item.level;
    }

    return ok(settings());
  }),
];
