import { isForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { orgParams, useSession } from "@/shared/model/session";

// 403 здесь не сбой, а роль: карточку, команду и приглашения отдают только
// создателю и администраторам, и повторы лишь задержали бы объяснение
const retry = (count: number, error: unknown) =>
  !isForbidden(error) && count < 3;

const refresh = (...paths: string[]) =>
  Promise.all(
    paths.map((path) =>
      queryClient.invalidateQueries({ queryKey: ["get", path] }),
    ),
  );

export const useOrgCard = () =>
  rqClient.useQuery(
    "get",
    "/api/admin/org",
    { params: orgParams() },
    { retry },
  );

export const useOrgSettings = () =>
  rqClient.useQuery("get", "/api/admin/org/settings", { params: orgParams() });

export const useOrgMembers = () =>
  rqClient.useQuery(
    "get",
    "/api/admin/org/members",
    { params: orgParams() },
    { retry },
  );

export const useOrgInvites = () =>
  rqClient.useQuery(
    "get",
    "/api/admin/org/invites",
    { params: orgParams() },
    { retry },
  );

// роль - по своей строке в команде: /me закэширован на всю сессию и не
// узнает о повышении по приглашению
export const useActorRole = () => {
  const { session, currentOrg } = useSession();
  const members = useOrgMembers();

  return (
    members.data?.find((member) => member.user_id === session?.user_id)?.role ??
    currentOrg?.role
  );
};

// окно показаний читает и карточка показаний дома
export const useSaveSettings = () =>
  rqClient.useMutation("put", "/api/admin/org/settings", {
    onSuccess: () =>
      refresh(
        "/api/admin/org/settings",
        "/api/admin/org",
        "/api/admin/houses/{house_id}/readings",
      ),
  });

export const useRemoveMember = () =>
  rqClient.useMutation("delete", "/api/admin/org/members/{user_id}", {
    onSettled: () => refresh("/api/admin/org/members", "/api/admin/org"),
  });

export const useCreateInvite = () =>
  rqClient.useMutation("post", "/api/admin/org/invites", {
    onSuccess: () => refresh("/api/admin/org/invites"),
  });

export const useRevokeInvite = () =>
  rqClient.useMutation("delete", "/api/admin/org/invites/{code}", {
    onSettled: () => refresh("/api/admin/org/invites"),
  });
