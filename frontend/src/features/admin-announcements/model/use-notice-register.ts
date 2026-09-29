import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";

import { isSending } from "../domain/labels";
import { useOrgHouses } from "./use-announcements";

export const useNoticeRegister = () => {
  const route = useRouteParams(
    z.object({ announcementId: z.coerce.number().int().positive() }),
  );
  const [houseId, setHouseId] = useState<number>();
  const [unmarkedOnly, setUnmarkedOnly] = useState(false);
  const houses = useOrgHouses();

  const register = rqClient.useQuery(
    "get",
    "/api/admin/announcements/{announcement_id}/register",
    {
      params: {
        ...orgParams(),
        path: { announcement_id: route?.announcementId ?? 0 },
        query: { house_id: houseId },
      },
    },
    {
      enabled: route !== null,
      placeholderData: keepPreviousData,
      refetchInterval: (query) =>
        query.state.data && isSending(query.state.data.announcement)
          ? 3000
          : false,
    },
  );

  const pdf = rqClient.useMutation(
    "post",
    "/api/admin/announcements/{announcement_id}/register/pdf",
  );

  const data = register.data;

  return {
    register: data,
    houses: (data?.announcement.house_ids ?? []).map((id) => ({
      id,
      address:
        houses.data?.items.find((house) => house.id === id)?.address ??
        `Дом №${id}`,
    })),
    pickHouse: (id: number) => {
      pdf.reset();
      setHouseId(id);
    },
    unmarkedOnly,
    setUnmarkedOnly: (value: boolean) => {
      pdf.reset();
      setUnmarkedOnly(value);
    },
    pdf,
    sendPdf: () => {
      if (data) {
        pdf.mutate({
          params: {
            ...orgParams(),
            path: { announcement_id: data.announcement.id },
            query: { house_id: data.house_id, unmarked_only: unmarkedOnly },
          },
        });
      }
    },
    flats: (data?.flats ?? []).filter(
      (flat) => !unmarkedOnly || !flat.delivered,
    ),
    isPending: route !== null && register.isPending,
    isError: route === null || register.isError,
    loadError: register.error,
    retry: () => void register.refetch(),
  };
};
