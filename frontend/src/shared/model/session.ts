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

export type OrgMembership = components["schemas"]["OrgMembership"];

const sessionQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me", { params: authParams() });

const SELECTED_KEY = "selected-residency";

const SELECTED_ORG_KEY = "selected-org";

const residencyOf = (residencies: Residency[], id: number | null) =>
  residencies.find((item) => item.resident_id === id) ?? residencies.at(-1);

export const currentResidency = (session: Session | undefined) =>
  residencyOf(
    session?.residencies ?? [],
    Number(localStorage.getItem(SELECTED_KEY)) || null,
  );

const orgOf = (orgs: OrgMembership[], id: number | null) =>
  orgs.find((item) => item.org_id === id) ?? orgs.at(-1);

export const currentOrg = (session: Session | undefined) =>
  orgOf(
    session?.orgs ?? [],
    Number(localStorage.getItem(SELECTED_ORG_KEY)) || null,
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

export const selectOrg = async (orgId: number) => {
  localStorage.setItem(SELECTED_ORG_KEY, String(orgId));
  dispatchStorageEvent({ key: SELECTED_ORG_KEY, storageArea: localStorage });

  await queryClient.invalidateQueries();
};

export const orgParams = () => ({
  header: {
    ...authParams().header,
    "X-Org-Id":
      currentOrg(queryClient.getQueryData(sessionQueryOptions().queryKey))
        ?.org_id ?? null,
  },
});

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
  const selectedOrg = useLocalStorage<number>(SELECTED_ORG_KEY);

  const currentResidency = residencyOf(
    residencies,
    selectedResidency.value ?? null,
  );

  const orgs = session?.orgs ?? [];

  const currentOrg = orgOf(orgs, selectedOrg.value ?? null);

  return {
    session,
    residencies,
    currentResidency,
    orgs,
    currentOrg,
    selectOrg,
    isConsentGiven: session?.consent_at != null,
    select: selectResidency,
    save: (next: Session) =>
      queryClient.setQueryData(sessionQueryOptions().queryKey, next),
    reload: () => queryClient.invalidateQueries(sessionQueryOptions()),
  };
};
