import { useQuery } from "@tanstack/react-query";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type Session = components["schemas"]["MeResponse"];

export type Residency = components["schemas"]["ResidencySummary"];

const sessionQueryOptions = () =>
  rqClient.queryOptions("get", "/api/me", { params: authParams() });

export const isOnboarded = (session: Session) =>
  session.consent_at !== null && session.residencies.length > 0;

export const loadSession = () =>
  queryClient.query({ ...sessionQueryOptions(), staleTime: "static" });

export const useSession = () => {
  const { data: session } = useQuery(sessionQueryOptions());
  const residencies = session?.residencies ?? [];

  return {
    session,
    residencies,
    currentResidency: residencies.at(-1),
    isConsentGiven: session?.consent_at != null,
    save: (next: Session) =>
      queryClient.setQueryData(sessionQueryOptions().queryKey, next),
    reload: () => queryClient.invalidateQueries(sessionQueryOptions()),
  };
};
