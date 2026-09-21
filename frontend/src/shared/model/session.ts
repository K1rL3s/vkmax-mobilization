import {
  dispatchStorageEvent,
  useLocalStorage,
} from "@siberiacancode/reactuse";
import { useQuery } from "@tanstack/react-query";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type Session = components["schemas"]["MeResponse"];

export type Residency = components["schemas"]["ResidencySummary"];

const sessionQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me", { params: authParams() });

const SELECTED_KEY = "selected-residency";

const residencyOf = (residencies: Residency[], id: number | null) =>
  residencies.find((item) => item.resident_id === id) ?? residencies.at(-1);

export const currentResidency = (session: Session | undefined) =>
  residencyOf(
    session?.residencies ?? [],
    Number(localStorage.getItem(SELECTED_KEY)) || null,
  );

export const isOnboarded = (session: Session) =>
  session.consent_at !== null && session.residencies.length > 0;

export const loadSession = () =>
  queryClient.query({ ...sessionQueryOptions(), staleTime: "static" });

export const selectResidency = async (residentId: number) => {
  localStorage.setItem(SELECTED_KEY, String(residentId));
  dispatchStorageEvent({ key: SELECTED_KEY, storageArea: localStorage });

  await queryClient.invalidateQueries();
};

export const forgetResidency = () => {
  localStorage.removeItem(SELECTED_KEY);
  dispatchStorageEvent({ key: SELECTED_KEY, storageArea: localStorage });
};

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

  const selectedResidency = useLocalStorage<number>(SELECTED_KEY);

  const currentResidency = residencyOf(
    residencies,
    selectedResidency.value ?? null,
  );

  return {
    session,
    residencies,
    currentResidency,
    isConsentGiven: session?.consent_at != null,
    select: selectResidency,
    save: (next: Session) =>
      queryClient.setQueryData(sessionQueryOptions().queryKey, next),
    reload: () => queryClient.invalidateQueries(sessionQueryOptions()),
  };
};
