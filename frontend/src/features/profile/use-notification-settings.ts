import { useQuery } from "@tanstack/react-query";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import {
  chartIcon,
  megaphoneIcon,
  meterIcon,
  wrenchIcon,
} from "@/shared/ui/icon";

type NotificationCategory = components["schemas"]["NotificationCategory"];

export type NotificationLevel = components["schemas"]["NotificationLevel"];

type Setting = components["schemas"]["NotificationSettingItem"];

export const CATEGORIES: {
  category: NotificationCategory;
  title: string;
  icon: string;
}[] = [
  { category: "requests", title: "Заявки", icon: wrenchIcon },
  { category: "announcements", title: "Объявления УК", icon: megaphoneIcon },
  { category: "meters", title: "Счётчики и поверка", icon: meterIcon },
  { category: "digest", title: "Недельная сводка", icon: chartIcon },
];

export const LEVEL_LABEL: Record<NotificationLevel, string> = {
  sound: "Со звуком",
  silent: "Без звука",
  off: "Выключены",
};

export const settingsQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me/notifications", {
    params: authParams(),
  });

export const useNotificationSettings = () => {
  const settings = useQuery(settingsQueryOptions());

  const update = rqClient.useMutation("put", "/api/me/notifications");

  const current: Setting[] =
    (update.isPending ? update.variables.body.settings : null) ??
    settings.data?.settings ??
    [];

  return {
    settings,
    levelOf: (category: NotificationCategory) =>
      current.find((item) => item.category === category)?.level,
    set: (category: NotificationCategory, level: NotificationLevel) =>
      update.mutate(
        {
          params: authParams(),
          body: {
            settings: [
              ...current.filter((item) => item.category !== category),
              { category, level },
            ],
          },
        },
        {
          onSuccess: (data) =>
            queryClient.setQueryData(settingsQueryOptions().queryKey, data),
        },
      ),
    isFailed: update.isError,
  };
};
