import { useEffect, useState } from "react";
import { keepPreviousData } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { requestCategorySchema } from "@/features/request";
import { retryUnlessForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import type { components } from "@/shared/api/schema/generated";
import { orgParams, useSession } from "@/shared/model/session";

import { houseSignature, STATES } from "../domain/map-filters";

export type AdminMapHouse = components["schemas"]["AdminMapHouse"];

type AdminMap = components["schemas"]["AdminMapResponse"];

export const QUICK_FILTERS = [
  { id: "urgent", label: "Срочное", adminOnly: false },
  { id: "poll", label: "Опрос", adminOnly: false },
  { id: "reception", label: "Приём сегодня", adminOnly: false },
  { id: "meters_low", label: "Счётчики < 50%", adminOnly: false },
  { id: "pending", label: "Ждут проверки", adminOnly: true },
] as const;

export const PLATFORM_KINDS = [
  { id: "connected", label: "Подключены" },
  { id: "unconnected", label: "Не подключены" },
  { id: "added", label: "Добавлены жителями" },
] as const;

const csv = <T extends string>(values: readonly { id: T }[]) =>
  z
    .string()
    .transform((value) =>
      values
        .map((item) => item.id)
        .filter((id) => value.split(",").includes(id)),
    )
    .catch([]);

const flag = z
  .string()
  .transform((value) => value === "1")
  .catch(false);

const range = z
  .string()
  .regex(/^(\d+-\d*|\d*-\d+)$/)
  .optional()
  .catch(undefined);

const filtersSchema = z.object({
  view: z.enum(["map", "list"]).catch("map"),
  color: z.enum(["requests", "meters", "residents"]).catch("requests"),
  heat: flag,
  platform: flag,
  states: csv(STATES),
  category: requestCategorySchema.optional().catch(undefined),
  period: z.enum(["week", "month", "quarter", "half"]).catch("month"),
  quick: csv(QUICK_FILTERS),
  pkind: csv(PLATFORM_KINDS),
  porg: z
    .string()
    .transform((value) =>
      value
        .split(",")
        .map(Number)
        .filter((id) => Number.isInteger(id) && id > 0),
    )
    .catch([]),
  pwait: flag,
  ontime: range,
  rating: range,
});

export type MapFilters = z.infer<typeof filtersSchema>;

type Param = keyof MapFilters;

const FILTER_PARAMS: Param[] = [
  "states",
  "category",
  "period",
  "quick",
  "pkind",
  "porg",
  "pwait",
  "ontime",
  "rating",
];

export const useAdminMap = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { currentOrg } = useSession();
  const isAdmin =
    currentOrg?.role === "creator" || currentOrg?.role === "admin";
  const parsed = filtersSchema.parse(Object.fromEntries(searchParams));
  const filters: MapFilters = {
    ...parsed,
    color: parsed.color === "residents" && !isAdmin ? "requests" : parsed.color,
    quick: parsed.quick.filter((id) => isAdmin || id !== "pending"),
  };
  const quick = new Set<string>(filters.quick);

  const query = {
    states: filters.states.length > 0 ? filters.states : undefined,
    category: filters.category,
    period: filters.period,
    urgent: quick.has("urgent") || undefined,
    poll: quick.has("poll") || undefined,
    reception_today: quick.has("reception") || undefined,
    meters_below: quick.has("meters_low") ? 50 : undefined,
    pending: quick.has("pending") || undefined,
  };
  const key = JSON.stringify(query);

  const houses = rqClient.useQuery(
    "get",
    "/api/admin/map/houses",
    { params: { ...orgParams(), query } },
    {
      enabled: filters.view === "map",
      refetchInterval: 10_000,
      placeholderData: keepPreviousData,
      retry: retryUnlessForbidden,
    },
  );

  const everyHouse = rqClient.useQuery(
    "get",
    "/api/admin/map/houses",
    { params: { ...orgParams(), query: { period: "month" } } },
    { enabled: filters.view === "map", retry: retryUnlessForbidden },
  );

  const [seen, setSeen] = useState<{
    data: AdminMap;
    key: string;
    pulseIds: number[];
  } | null>(null);
  const fresh = houses.isPlaceholderData ? undefined : houses.data;

  if (fresh && fresh !== seen?.data) {
    const before =
      seen?.key === key
        ? new Map(
            seen.data.items.map((house) => [house.id, houseSignature(house)]),
          )
        : null;
    setSeen({
      data: fresh,
      key,
      pulseIds: before
        ? fresh.items
            .filter(
              (house) =>
                before.has(house.id) &&
                before.get(house.id) !== houseSignature(house),
            )
            .map((house) => house.id)
        : [],
    });
  }

  const pulseCount = seen?.pulseIds.length ?? 0;

  useEffect(() => {
    if (pulseCount === 0) return;
    const timer = setTimeout(
      () => setSeen((current) => current && { ...current, pulseIds: [] }),
      3000,
    );
    return () => clearTimeout(timer);
  }, [seen?.data, pulseCount]);

  const update = (patch: Partial<Record<Param, string | null>>) =>
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [name, value] of Object.entries(patch)) {
          if (value) next.set(name, value);
          else next.delete(name);
        }
        return next;
      },
      { replace: true },
    );

  const toggle = (
    name: "states" | "quick" | "pkind" | "porg",
    id: string | number,
  ) => {
    const current = filters[name].map(String);
    const next = current.includes(String(id))
      ? current.filter((item) => item !== String(id))
      : [...current, String(id)];
    update({ [name]: next.join(",") || null });
  };

  const platformFiltered =
    filters.pkind.length > 0 ||
    filters.porg.length > 0 ||
    filters.pwait ||
    Boolean(filters.ontime) ||
    Boolean(filters.rating);

  return {
    filters,
    isAdmin,
    houses,
    fitItems: everyHouse.data?.items ?? houses.data?.items,
    isFitting: everyHouse.isPending,
    pulseIds: seen?.pulseIds ?? [],
    hasFilters:
      filters.states.length > 0 ||
      Boolean(filters.category) ||
      filters.period !== "month" ||
      filters.quick.length > 0 ||
      (filters.platform && platformFiltered),
    update,
    toggle,
    reset: () =>
      update(Object.fromEntries(FILTER_PARAMS.map((name) => [name, null]))),
  };
};

export type AdminMapModel = ReturnType<typeof useAdminMap>;
