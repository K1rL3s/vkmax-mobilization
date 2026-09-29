import { useMemo } from "react";
import { keepPreviousData } from "@tanstack/react-query";

import { authParams, rqClient } from "@/shared/api/instance";
import type { components } from "@/shared/api/schema/generated";
import { useSession } from "@/shared/model/session";
import type { MapBounds } from "@/shared/ui/map";

import { parseRange } from "../domain/map-filters";
import type { MapFilters } from "./use-admin-map";

export type PlatformHouse = components["schemas"]["MapHouse"];

const within = (value: number | undefined, max: number) =>
  value === undefined ? undefined : Math.min(value, max);

const clampBounds = ({ west, south, east, north }: MapBounds) => ({
  west: Math.max(west, -180),
  south: Math.max(south, -90),
  east: Math.min(east, 180),
  north: Math.min(north, 90),
});

export const usePlatformMap = (
  filters: MapFilters,
  bounds: MapBounds | null,
) => {
  const { currentOrg } = useSession();
  const [onTimeFrom, onTimeTo] = parseRange(filters.ontime, 100);
  const [ratingFrom, ratingTo] = parseRange(filters.rating, 10);

  const houses = rqClient.useQuery(
    "get",
    "/api/map/houses",
    {
      params: {
        ...authParams(),
        query: {
          ...clampBounds(bounds ?? { west: 0, south: 0, east: 0, north: 0 }),
          kinds: filters.pkind.length > 0 ? filters.pkind : undefined,
          org_ids: filters.porg.length > 0 ? filters.porg : undefined,
          waiting: filters.pwait || undefined,
          on_time_from: within(onTimeFrom, 10_000),
          on_time_to: within(onTimeTo, 10_000),
          rating_from: within(ratingFrom, 500),
          rating_to: within(ratingTo, 500),
        },
      },
    },
    {
      enabled: filters.platform && bounds !== null,
      placeholderData: keepPreviousData,
    },
  );

  const orgId = currentOrg?.org_id;
  const data = filters.platform ? houses.data : undefined;

  const visible = useMemo(
    () => ({
      items: data?.items.filter((house) => house.org_id !== orgId) ?? [],
      orgs: data?.orgs.filter((org) => org.id !== orgId) ?? [],
    }),
    [data, orgId],
  );

  return { ...visible, isError: filters.platform && houses.isError };
};
