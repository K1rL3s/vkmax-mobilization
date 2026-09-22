import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type FlatInvite = components["schemas"]["FlatInviteItem"];

export type FlatResident = components["schemas"]["FlatResidentItem"];

const invitesOptions = (flatId: number) =>
  rqClient.queryOptions("get", "/api/flats/{flat_id}/invites", {
    params: { ...authParams(), path: { flat_id: flatId } },
  });

// бэк отдаёт и отозванные, и истёкшие, и исчерпанные коды: владельцу нужны
// только те, по которым арендатор ещё может войти
const isLive = (invite: FlatInvite, now: number) =>
  invite.revoked_at === null &&
  Date.parse(invite.expires_at) > now &&
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
      select: (invites) => invites.filter((item) => isLive(item, Date.now())),
    },
  );

const refreshInvites = (flatId: number) =>
  queryClient.invalidateQueries({ queryKey: invitesOptions(flatId).queryKey });

export const useIssueInvite = (flatId: number) =>
  rqClient.useMutation("post", "/api/flats/{flat_id}/invites", {
    onSuccess: () => refreshInvites(flatId),
  });

export const useRevokeInvite = (flatId: number) =>
  rqClient.useMutation("delete", "/api/flat-invites/{code}", {
    onSuccess: () => refreshInvites(flatId),
  });
