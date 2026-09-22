import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";

export type Announcement = components["schemas"]["AnnouncementItem"];

export type OrgHouse = components["schemas"]["AdminHouseListItem"];

// ponytail: первые 100 домов (предел страницы бэка), выбор из остальных - когда у УК их станет больше
export const useOrgHouses = () =>
  rqClient.useQuery("get", "/api/admin/houses", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

export const useAnnouncementList = () => {
  const houses = useOrgHouses();
  const announcements = rqClient.useInfiniteQuery(
    "get",
    "/api/admin/announcements",
    { params: { ...orgParams(), query: { limit: 20 } } },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: (last, pages) => {
        const loaded = pages.reduce((sum, page) => sum + page.items.length, 0);

        return loaded < last.total ? loaded : undefined;
      },
    },
  );

  return {
    houses: houses.data?.items ?? [],
    items: announcements.data?.pages.flatMap((page) => page.items) ?? [],
    isPending: announcements.isPending,
    isError: announcements.isError,
    retry: () => void announcements.refetch(),
    hasMore: announcements.hasNextPage,
    isLoadingMore: announcements.isFetchingNextPage,
    loadMore: () => void announcements.fetchNextPage(),
  };
};

const sentSchema = z.object({
  sent: z.object({
    recipients: z.number().int().nonnegative(),
    withoutChat: z.array(z.string()),
  }),
});

export type SentOutcome = z.infer<typeof sentSchema>["sent"];

export const sentState = (sent: SentOutcome) => ({ sent });

// итог отправки приезжает состоянием навигации, а оно переживает перезагрузку
// и возврат назад: читаем один раз и сразу стираем из истории
export const useSentOutcome = () => {
  const { state, pathname } = useLocation();
  const navigate = useNavigate();
  const [sent, setSent] = useState(
    () => sentSchema.safeParse(state).data?.sent ?? null,
  );

  useEffect(() => {
    if (state !== null) {
      void navigate(pathname, { replace: true, state: null });
    }
  }, [state, pathname, navigate]);

  return { sent, dismiss: () => setSent(null) };
};
