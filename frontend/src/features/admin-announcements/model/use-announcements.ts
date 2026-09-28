import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import { nextOffset } from "@/shared/api/next-offset";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";

import { isSending } from "../domain/labels";

export type Announcement = components["schemas"]["AnnouncementItem"];

export type OrgHouse = components["schemas"]["AdminHouseListItem"];

export const useOrgHouses = () =>
  rqClient.useQuery("get", "/api/admin/houses", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

const houseFilterSchema = z.coerce
  .number()
  .int()
  .positive()
  .optional()
  .catch(undefined);

export const useAnnouncementList = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const houseId = houseFilterSchema.parse(
    searchParams.get("house") ?? undefined,
  );
  const houses = useOrgHouses();
  const announcements = rqClient.useInfiniteQuery(
    "get",
    "/api/admin/announcements",
    { params: { ...orgParams(), query: { limit: 20, house_id: houseId } } },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: nextOffset,
      refetchInterval: (query) =>
        query.state.data?.pages[0]?.items.some(isSending) ? 3000 : false,
    },
  );

  return {
    houseId,
    houseAddress: houses.data?.items.find((house) => house.id === houseId)
      ?.address,
    clearHouse: () => setSearchParams({}, { replace: true }),
    houses: houses.data?.items ?? [],
    items: announcements.data?.pages.flatMap((page) => page.items) ?? [],
    isPending: announcements.isPending,
    isError: announcements.isError,
    loadError: announcements.error,
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
