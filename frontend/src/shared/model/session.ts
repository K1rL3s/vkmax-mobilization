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

export type Cabinet = "resident" | "admin";

export type Selection = {
  cabinet: Cabinet;
  residentId: number | null;
  orgId: number | null;
};

export type StartTarget = "admin" | "home" | "onboarding";

const sessionQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me", { params: authParams() });

const SELECTION_KEY = "selection";

const idOf = (value: unknown) =>
  typeof value === "number" && Number.isSafeInteger(value) && value > 0
    ? value
    : null;

const selectionOf = (stored: unknown): Selection => {
  const value = (stored ?? {}) as Partial<Record<keyof Selection, unknown>>;

  return {
    cabinet: value.cabinet === "admin" ? "admin" : "resident",
    residentId: idOf(value.residentId),
    orgId: idOf(value.orgId),
  };
};

const storedSelection = (): Selection => {
  const raw = localStorage.getItem(SELECTION_KEY);

  try {
    return selectionOf(raw === null ? null : JSON.parse(raw));
  } catch {
    return selectionOf(null);
  }
};

const writeSelection = (patch: Partial<Selection>) => {
  localStorage.setItem(
    SELECTION_KEY,
    JSON.stringify({ ...storedSelection(), ...patch }),
  );
  dispatchStorageEvent({ key: SELECTION_KEY, storageArea: localStorage });
};

const residencyOf = (residencies: Residency[], id: number | null) =>
  residencies.find((item) => item.resident_id === id) ?? residencies.at(-1);

export const currentResidency = (session: Session | undefined) =>
  residencyOf(session?.residencies ?? [], storedSelection().residentId);

const working = (orgs: OrgMembership[]) =>
  orgs.filter((org) => org.role !== "executor");

const orgOf = (orgs: OrgMembership[], id: number | null) =>
  orgs.find((item) => item.org_id === id) ?? working(orgs).at(-1);

export const currentOrg = (session: Session | undefined) =>
  orgOf(session?.orgs ?? [], storedSelection().orgId);

export const isOnboarded = (session: Session) =>
  session.consent_at !== null && session.residencies.length > 0;

export const workingOrgs = (session: Session | undefined) =>
  working(session?.orgs ?? []);

export const hasWorkingOrg = (session: Session | undefined) =>
  workingOrgs(session).length > 0;

export const startTarget = (
  session: Session,
  selection: Selection = storedSelection(),
): StartTarget => {
  if (session.consent_at === null) {
    return "onboarding";
  }

  if (
    hasWorkingOrg(session) &&
    (selection.cabinet === "admin" || session.residencies.length === 0)
  ) {
    return "admin";
  }

  return session.residencies.length > 0 ? "home" : "onboarding";
};

export const loadSession = () =>
  queryClient.query({ ...sessionQueryOptions(), staleTime: Infinity });

export const reloadSession = async () => {
  await queryClient.invalidateQueries(sessionQueryOptions());

  return loadSession();
};

export const selectResidency = async (residentId: number) => {
  writeSelection({ residentId });

  await queryClient.invalidateQueries();
};

export const forgetResidency = () => {
  writeSelection({ residentId: null });
};

export const selectOrg = async (orgId: number) => {
  writeSelection({ orgId });

  await queryClient.invalidateQueries();
};

export const selectCabinet = (cabinet: Cabinet) => {
  writeSelection({ cabinet });
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
  const orgs = session?.orgs ?? [];

  const selection = selectionOf(
    useLocalStorage<Selection>(SELECTION_KEY).value,
  );

  return {
    session,
    residencies,
    currentResidency: residencyOf(residencies, selection.residentId),
    orgs,
    currentOrg: orgOf(orgs, selection.orgId),
    cabinet: selection.cabinet,
    selectCabinet,
    selectOrg,
    isConsentGiven: session?.consent_at != null,
    select: selectResidency,
    save: (next: Session) =>
      queryClient.setQueryData(sessionQueryOptions().queryKey, next),
    reload: reloadSession,
  };
};
