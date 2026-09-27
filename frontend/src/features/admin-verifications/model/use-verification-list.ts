import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";
import type { StatusPillTone } from "@/shared/ui/status-pill";

export type VerificationRequest =
  components["schemas"]["VerificationRequestItem"];

export type StatusFilterId = "pending" | "decided" | "all";

const isWaiting = (request: VerificationRequest) =>
  request.status === "pending";

const useVerificationQueue = () =>
  rqClient.useQuery("get", "/api/admin/verification-requests", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

export const useVerificationList = () => {
  const [status, setStatus] = useState<StatusFilterId>("all");
  const [searchParams] = useSearchParams();
  const requests = useVerificationQueue();

  const houses = rqClient.useQuery("get", "/api/admin/houses", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

  const houseId = z.coerce
    .number()
    .int()
    .positive()
    .safeParse(searchParams.get("house_id")).data;

  const items = requests.data?.items ?? [];
  const total = requests.data?.total ?? 0;
  const byHouse =
    houseId === undefined
      ? items
      : items.filter((item) => item.house_id === houseId);
  const visible = byHouse.filter(
    (item) => status === "all" || isWaiting(item) === (status === "pending"),
  );

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
    loadError: requests.error,
    retry: () => void requests.refetch(),
    items: [
      ...visible
        .filter(isWaiting)
        .sort((a, b) => a.created_at.localeCompare(b.created_at)),
      ...visible
        .filter((item) => !isWaiting(item))
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    ],
    isEmpty: items.length === 0,
    isHouseEmpty: items.length > 0 && byHouse.length === 0,
    isFilterEmpty: byHouse.length > 0 && visible.length === 0,
    total,
    loaded: items.length,
    isTruncated: total > items.length,
  };
};

export const useVerificationRequest = (id: number | null) => {
  const requests = useVerificationQueue();

  return {
    isPending: requests.isPending,
    isError: requests.isError,
    loadError: requests.error,
    retry: () => void requests.refetch(),
    request: requests.data?.items.find((item) => item.id === id) ?? null,
  };
};

export const STATUS: Record<
  VerificationRequest["status"],
  { label: string; tone: StatusPillTone }
> = {
  pending: { label: "Ждёт решения", tone: "themed" },
  approved: { label: "Подтверждён", tone: "positive" },
  rejected: { label: "Отклонён", tone: "negative" },
};
