import { useMemo, useState } from "react";
import { useDebounceState } from "@siberiacancode/reactuse";
import { keepPreviousData } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { authParams, rqClient } from "@/shared/api/instance";
import type { MapBounds, MapFocus, MapPoint } from "@/shared/ui/map";

export const MAP_KINDS = [
  { id: "all", label: "Все" },
  { id: "connected", label: "Подключённые" },
  { id: "waiting", label: "Где ждут УК" },
] as const;

export type MapKind = (typeof MAP_KINDS)[number]["id"];

const filterSchema = z.object({
  kind: z.enum(["all", "connected", "waiting"]).catch("all"),
  org: z
    .string()
    .transform((value) =>
      value
        .split(",")
        .map(Number)
        .filter((id) => Number.isSafeInteger(id) && id > 0),
    )
    .catch([]),
});

export const usePublicMap = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filterSchema.parse(Object.fromEntries(searchParams));
  const [bounds, setBounds] = useDebounceState<MapBounds | null>(null, 300);
  const [zoom, setZoom] = useState(0);
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [isLocating, setLocating] = useState(false);
  const [isLocateFailed, setLocateFailed] = useState(false);

  const houses = rqClient.useQuery(
    "get",
    "/api/map/houses",
    {
      params: {
        ...authParams(),
        query: {
          ...(bounds ?? { west: 0, south: 0, east: 0, north: 0 }),
          kinds: filters.kind === "connected" ? ["connected"] : undefined,
          waiting: filters.kind === "waiting" || undefined,
          org_ids: filters.org.length > 0 ? filters.org : undefined,
        },
      },
    },
    {
      enabled: bounds !== null,
      refetchInterval: 10_000,
      placeholderData: keepPreviousData,
    },
  );

  const items = houses.data?.items;
  const points = useMemo(
    () =>
      (items ?? []).map((house): MapPoint => ({
        id: house.id,
        lat: house.lat,
        lon: house.lon,
        tone: house.kind === "connected" ? "brand" : "muted",
        label: house.building,
      })),
    [items],
  );

  const updateFilters = (kind: MapKind, org: readonly number[]) =>
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (kind === "all") next.delete("kind");
        else next.set("kind", kind);
        if (org.length === 0) next.delete("org");
        else next.set("org", org.join(","));
        return next;
      },
      { replace: true },
    );

  return {
    points,
    houses: items ?? [],
    total: houses.data?.total,
    orgs: houses.data?.orgs ?? [],
    isError: houses.isError && !houses.data,
    retry: () => void houses.refetch(),
    kind: filters.kind,
    org: filters.org,
    hasFilters: filters.kind !== "all" || filters.org.length > 0,
    changeKind: (kind: MapKind) => updateFilters(kind, filters.org),
    toggleOrg: (id: number) =>
      updateFilters(
        filters.kind,
        filters.org.includes(id)
          ? filters.org.filter((chosen) => chosen !== id)
          : [...filters.org, id],
      ),
    resetFilters: () => updateFilters("all", []),
    changeView: (next: MapBounds, nextZoom: number) => {
      setBounds(next);
      setZoom(nextZoom);
    },
    isZoomedOut: zoom < 15,
    focus,
    flyTo: (next: MapFocus) => {
      setLocateFailed(false);
      setFocus(next);
    },
    isLocating,
    isLocateFailed,
    locate: () => {
      setLocateFailed(false);
      if (!("geolocation" in navigator)) {
        setLocateFailed(true);
        return;
      }
      setLocating(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocating(false);
          setFocus({
            lat: position.coords.latitude,
            lon: position.coords.longitude,
            zoom: 16,
          });
        },
        () => {
          setLocating(false);
          setLocateFailed(true);
        },
        { enableHighAccuracy: true, timeout: 10_000 },
      );
    },
  };
};
