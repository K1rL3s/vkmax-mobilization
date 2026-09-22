import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";

export type VerificationRequest =
  components["schemas"]["VerificationRequestItem"];

export type StatusFilterId = "pending" | "decided" | "all";

const PAGE_LIMIT = 100;

const houseIdSchema = z.coerce.number().int().positive();

const isWaiting = (request: VerificationRequest) =>
  request.status === "pending";

const matchesStatus = (
  request: VerificationRequest,
  filter: StatusFilterId,
) => {
  if (filter === "all") {
    return true;
  }

  return filter === "pending" ? isWaiting(request) : !isWaiting(request);
};

const oldestFirst = (a: VerificationRequest, b: VerificationRequest) =>
  a.created_at.localeCompare(b.created_at);

const newestFirst = (a: VerificationRequest, b: VerificationRequest) =>
  b.created_at.localeCompare(a.created_at);

const order = (items: VerificationRequest[]) => {
  const waiting = items.filter(isWaiting).sort(oldestFirst);
  const decided = items.filter((item) => !isWaiting(item)).sort(newestFirst);

  return [...waiting, ...decided];
};

export const useVerificationList = () => {
  const [status, setStatus] = useState<StatusFilterId>("all");
  const [searchParams] = useSearchParams();

  const requests = rqClient.useQuery(
    "get",
    "/api/admin/verification-requests",
    { params: { ...orgParams(), query: { limit: PAGE_LIMIT } } },
  );

  const houses = rqClient.useQuery("get", "/api/admin/houses", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

  const houseId = houseIdSchema.safeParse(searchParams.get("house_id")).data;

  const items = requests.data?.items ?? [];
  const total = requests.data?.total ?? 0;
  const byHouse =
    houseId === undefined
      ? items
      : items.filter((item) => item.house_id === houseId);
  const visible = byHouse.filter((item) => matchesStatus(item, status));

  return {
    status,
    setStatus,
    houseId: houseId ?? null,
    houseAddress:
      houses.data?.items.find((house) => house.id === houseId)?.address ??
      byHouse.at(0)?.address ??
      null,
    isPending: requests.isPending,
    isError: requests.isError,
    retry: () => void requests.refetch(),
    items: order(visible),
    isEmpty: items.length === 0,
    isHouseEmpty: items.length > 0 && byHouse.length === 0,
    isFilterEmpty: byHouse.length > 0 && visible.length === 0,
    total,
    loaded: items.length,
    isTruncated: total > items.length,
  };
};

// карточки запроса на бэке нет, только список
export const useVerificationRequest = (id: number | null) => {
  const requests = rqClient.useQuery(
    "get",
    "/api/admin/verification-requests",
    { params: { ...orgParams(), query: { limit: PAGE_LIMIT } } },
  );

  return {
    isPending: requests.isPending,
    isError: requests.isError,
    retry: () => void requests.refetch(),
    request: requests.data?.items.find((item) => item.id === id) ?? null,
  };
};
