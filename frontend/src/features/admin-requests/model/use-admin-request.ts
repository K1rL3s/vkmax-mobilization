import { z } from "zod";

import { isForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";

const retryUnlessForbidden = (count: number, error: unknown) =>
  !isForbidden(error) && count < 3;

export const useAdminRequest = () => {
  const params = useRouteParams(
    z.object({ requestId: z.coerce.number().int().positive() }),
  );
  const request = rqClient.useQuery(
    "get",
    "/api/admin/requests/{request_id}",
    {
      params: { ...orgParams(), path: { request_id: params?.requestId ?? 0 } },
    },
    { enabled: params !== null, retry: retryUnlessForbidden },
  );

  const retry = () => void request.refetch();

  return {
    valid: params !== null,
    request: request.data,
    isForbidden: isForbidden(request.error),
    isPending: request.isPending,
    isError: request.isError,
    retry,
  };
};

export const useAdminRequestGroup = () => {
  const params = useRouteParams(
    z.object({ groupId: z.coerce.number().int().positive() }),
  );
  const group = rqClient.useQuery(
    "get",
    "/api/admin/request-groups/{group_id}",
    {
      params: { ...orgParams(), path: { group_id: params?.groupId ?? 0 } },
    },
    { enabled: params !== null, retry: retryUnlessForbidden },
  );

  const retry = () => void group.refetch();

  return {
    valid: params !== null,
    group: group.data,
    isForbidden: isForbidden(group.error),
    isPending: group.isPending,
    isError: group.isError,
    retry,
  };
};
