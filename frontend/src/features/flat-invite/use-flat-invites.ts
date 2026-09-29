import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths, queryClient } from "@/shared/api/query-client";

export type FlatInvite = components["schemas"]["FlatInviteItem"];

export type FlatResident = components["schemas"]["FlatResidentItem"];

const isLive = (invite: FlatInvite) =>
  invite.revoked_at === null &&
  Date.parse(invite.expires_at) > Date.now() &&
  invite.activations_used < invite.max_activations;

export const useFlatResidents = (flatId: number) =>
  rqClient.useQuery("get", "/api/flats/{flat_id}/residents", {
    params: { ...authParams(), path: { flat_id: flatId } },
  });

export const useFlatInvites = (flatId: number) =>
  rqClient.useQuery(
    "get",
    "/api/flats/{flat_id}/invites",
    { params: { ...authParams(), path: { flat_id: flatId } } },
    {
      select: (invites) => invites.filter(isLive),
    },
  );

const refreshInvites = (flatId: number) =>
  queryClient.invalidateQueries({
    queryKey: rqClient.queryOptions("get", "/api/flats/{flat_id}/invites", {
      params: { ...authParams(), path: { flat_id: flatId } },
    }).queryKey,
  });

export const useIssueInvite = (flatId: number) =>
  rqClient.useMutation("post", "/api/flats/{flat_id}/invites", {
    onSuccess: () => refreshInvites(flatId),
  });

export const useRevokeInvite = (flatId: number) =>
  rqClient.useMutation("delete", "/api/flat-invites/{code}", {
    onSuccess: () => refreshInvites(flatId),
  });

export const useFlatTenancies = (flatId: number) =>
  rqClient.useQuery(
    "get",
    "/api/flats/{flat_id}/tenancies",
    { params: { ...authParams(), path: { flat_id: flatId } } },
    {
      select: (tenancies) =>
        tenancies.flatMap(({ ended_at, ...tenancy }) =>
          ended_at === null ? [] : [{ ...tenancy, ended_at }],
        ),
    },
  );

export const useEndTenancy = () =>
  rqClient.useMutation("delete", "/api/flats/{flat_id}/tenants/{resident_id}", {
    onSuccess: () =>
      invalidatePaths(
        "/api/flats/{flat_id}",
        "/api/flats/{flat_id}/residents",
        "/api/flats/{flat_id}/tenancies",
        "/api/flats/{flat_id}/invites",
      ),
  });
