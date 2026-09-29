import { useSyncExternalStore } from "react";
import {
  dispatchStorageEvent,
  useLocalStorage,
} from "@siberiacancode/reactuse";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type Session = components["schemas"]["MeResponse"];

export type Residency = components["schemas"]["ResidencySummary"];

const sessionQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me", { params: authParams() });

const cachedSession = () =>
  queryClient.getQueryData<Session>(sessionQueryOptions().queryKey);

const SELECTION_KEY = "selection";

const idSchema = z.number().int().positive().nullable().catch(null);

const selectionSchema = z
  .object({
    cabinet: z.enum(["resident", "admin"]).catch("resident"),
    residentId: idSchema,
    orgId: idSchema,
  })
  .catch({ cabinet: "resident", residentId: null, orgId: null });

type Selection = z.infer<typeof selectionSchema>;

const storedSelection = () => {
  try {
    return selectionSchema.parse(
      JSON.parse(localStorage.getItem(SELECTION_KEY) ?? "null"),
    );
  } catch {
    return selectionSchema.parse(null);
  }
};

const writeSelection = (patch: Partial<Selection>) => {
  localStorage.setItem(
    SELECTION_KEY,
    JSON.stringify({ ...storedSelection(), ...patch }),
  );
  dispatchStorageEvent({ key: SELECTION_KEY, storageArea: localStorage });
};

const residencyOf = (session: Session | undefined, id: number | null) =>
  session?.residencies.find((item) => item.resident_id === id) ??
  session?.residencies.at(-1);

export const currentResidency = (session: Session | undefined) =>
  residencyOf(session, storedSelection().residentId);

export const workingOrgs = (session: Session | undefined) =>
  (session?.orgs ?? []).filter((org) => org.role !== "executor");

const orgOf = (session: Session | undefined, id: number | null) =>
  session?.orgs.find((item) => item.org_id === id) ??
  workingOrgs(session).at(-1);

export const isOnboarded = (session: Session) =>
  session.consent_at !== null && session.residencies.length > 0;

export const hasWorkingOrg = (session: Session) =>
  workingOrgs(session).length > 0;

export const startTarget = (session: Session) => {
  if (session.consent_at === null) {
    return "onboarding";
  }

  if (
    hasWorkingOrg(session) &&
    (storedSelection().cabinet === "admin" || session.residencies.length === 0)
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

export const selectCabinet = (cabinet: Selection["cabinet"]) => {
  writeSelection({ cabinet });
};

export const orgParams = () => ({
  header: {
    ...authParams().header,
    "X-Org-Id": orgOf(cachedSession(), storedSelection().orgId)?.org_id ?? null,
  },
});

export const houseParams = () => ({
  header: {
    ...authParams().header,
    "X-House-Id": currentResidency(cachedSession())?.house_id ?? null,
  },
});

export const useSession = () => {
  const { data: session } = useQuery(sessionQueryOptions());
  const selection = selectionSchema.parse(useLocalStorage(SELECTION_KEY).value);

  return {
    session,
    residencies: session?.residencies ?? [],
    currentResidency: residencyOf(session, selection.residentId),
    currentOrg: orgOf(session, selection.orgId),
    selectCabinet,
    selectOrg,
    isConsentGiven: session?.consent_at != null,
    select: selectResidency,
    save: (next: Session) =>
      queryClient.setQueryData(sessionQueryOptions().queryKey, next),
    reload: reloadSession,
  };
};

export const useTextSize = () =>
  useSyncExternalStore(
    (onChange) => queryClient.getQueryCache().subscribe(onChange),
    () => cachedSession()?.text_size ?? "normal",
  );
