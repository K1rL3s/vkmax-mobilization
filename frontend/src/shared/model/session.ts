import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type Session = components["schemas"]["MeResponse"];

export type Residency = components["schemas"]["ResidencySummary"];

const sessionQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me", { params: authParams() });

const SELECTED_KEY = "selected-residency";

// хранилище отдаёт что угодно, поэтому привязка проверяется схемой; в
// приватном окне доступа к нему может не быть вовсе
const readSelected = (): number | null => {
  try {
    const stored = z.coerce
      .number()
      .int()
      .positive()
      .safeParse(localStorage.getItem(SELECTED_KEY));

    return stored.success ? stored.data : null;
  } catch {
    return null;
  }
};

let selectedId = readSelected();

const listeners = new Set<() => void>();

const subscribe = (listener: () => void) => {
  listeners.add(listener);

  return () => {
    listeners.delete(listener);
  };
};

const getSelectedId = () => selectedId;

// адрес, из которого житель смотрит кабинет: выбранный им или, пока выбора не
// было, последняя привязка - она же единственная у жителя одного дома
const residencyOf = (residencies: Residency[], id: number | null) =>
  residencies.find((item) => item.resident_id === id) ?? residencies.at(-1);

export const currentResidency = (session: Session | undefined) =>
  residencyOf(session?.residencies ?? [], selectedId);

export const isOnboarded = (session: Session) =>
  session.consent_at !== null && session.residencies.length > 0;

export const loadSession = () =>
  queryClient.query({ ...sessionQueryOptions(), staleTime: "static" });

/**
 * Переключает адрес кабинета. Весь загруженный кабинет - заявки, счётчики,
 * карточка дома - относится к прошлому адресу, поэтому кэш сбрасывается
 * целиком, а не по одному ключу.
 */
export const selectResidency = async (residentId: number) => {
  selectedId = residentId;

  try {
    localStorage.setItem(SELECTED_KEY, String(residentId));
  } catch {
    // приватное окно: выбор доживёт до закрытия мини-аппа
  }

  listeners.forEach((listener) => listener());

  await queryClient.invalidateQueries();
};

/**
 * Параметры запроса, который бэк исполняет в контексте дома. Житель
 * нескольких домов без заголовка получит 403, поэтому дом уезжает всегда -
 * рядом с авторизацией, а не отдельной заботой каждой ручки.
 */
export const houseParams = () => ({
  header: {
    ...authParams().header,
    "X-House-Id":
      currentResidency(queryClient.getQueryData(sessionQueryOptions().queryKey))
        ?.house_id ?? null,
  },
});

export const useSession = () => {
  const { data: session } = useQuery(sessionQueryOptions());
  const residencies = session?.residencies ?? [];
  // выбор живёт вне react-query, но экраны обязаны перерисоваться на смену
  const selected = useSyncExternalStore(subscribe, getSelectedId);

  return {
    session,
    residencies,
    currentResidency: residencyOf(residencies, selected),
    isConsentGiven: session?.consent_at != null,
    select: selectResidency,
    save: (next: Session) =>
      queryClient.setQueryData(sessionQueryOptions().queryKey, next),
    reload: () => queryClient.invalidateQueries(sessionQueryOptions()),
  };
};
