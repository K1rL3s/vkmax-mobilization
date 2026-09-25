import { retryUnlessForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { orgParams, useSession } from "@/shared/model/session";

export const useOrgCard = () =>
  rqClient.useQuery(
    "get",
    "/api/admin/org",
    { params: orgParams() },
    { retry: retryUnlessForbidden },
  );

export const useOrgSettings = () =>
  rqClient.useQuery("get", "/api/admin/org/settings", { params: orgParams() });

export const useOrgMembers = () =>
  rqClient.useQuery(
    "get",
    "/api/admin/org/members",
    { params: orgParams() },
    { retry: retryUnlessForbidden },
  );

export const useOrgInvites = () =>
  rqClient.useQuery(
    "get",
    "/api/admin/org/invites",
    { params: orgParams() },
    { retry: retryUnlessForbidden },
  );

export const useActorRole = () => {
  const { session, currentOrg } = useSession();
  const members = useOrgMembers();

  return (
    members.data?.find((member) => member.user_id === session?.user_id)?.role ??
    currentOrg?.role
  );
};

export const useSaveSettings = () =>
  rqClient.useMutation("put", "/api/admin/org/settings", {
    onSuccess: () =>
      invalidatePaths(
        "/api/admin/org/settings",
        "/api/admin/org",
        "/api/admin/houses/{house_id}/readings",
      ),
  });

export const useRemoveMember = () =>
  rqClient.useMutation("delete", "/api/admin/org/members/{user_id}", {
    onSettled: () =>
      invalidatePaths("/api/admin/org/members", "/api/admin/org"),
  });

export const useCreateInvite = () =>
  rqClient.useMutation("post", "/api/admin/org/invites", {
    onSuccess: () => invalidatePaths("/api/admin/org/invites"),
  });

export const useRevokeInvite = () =>
  rqClient.useMutation("delete", "/api/admin/org/invites/{code}", {
    onSettled: () => invalidatePaths("/api/admin/org/invites"),
  });
