import { useQuery } from "@tanstack/react-query";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type Session = components["schemas"]["MeResponse"];

export type Residency = components["schemas"]["ResidencySummary"];

const sessionQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me", { params: authParams() });

// дом привязки, из которого житель смотрит кабинет: пока свитчера домов нет,
// это последняя привязка
const activeResidency = (session: Session | undefined) =>
  session?.residencies.at(-1);

export const isOnboarded = (session: Session) =>
  session.consent_at !== null && session.residencies.length > 0;

export const loadSession = () =>
  queryClient.query({ ...sessionQueryOptions(), staleTime: "static" });

/**
 * Параметры запроса, который бэк исполняет в контексте дома. Житель
 * нескольких домов без заголовка получит 403, поэтому дом уезжает всегда -
 * рядом с авторизацией, а не отдельной заботой каждой ручки.
 */
export const houseParams = () => ({
  header: {
    ...authParams().header,
    "X-House-Id":
      activeResidency(queryClient.getQueryData(sessionQueryOptions().queryKey))
        ?.house_id ?? null,
  },
});

export const useSession = () => {
  const { data: session } = useQuery(sessionQueryOptions());
  const residencies = session?.residencies ?? [];

  return {
    session,
    residencies,
    currentResidency: activeResidency(session),
    isConsentGiven: session?.consent_at != null,
    save: (next: Session) =>
      queryClient.setQueryData(sessionQueryOptions().queryKey, next),
    reload: () => queryClient.invalidateQueries(sessionQueryOptions()),
  };
};
