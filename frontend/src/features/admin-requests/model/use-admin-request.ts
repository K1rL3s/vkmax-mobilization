import { z } from "zod";

import { retryUnlessForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";

export const useAdminRequest = () => {
  const params = useRouteParams(
    z.object({ requestId: z.coerce.number().int().positive() }),
  );
  const query = rqClient.useQuery(
    "get",
    "/api/admin/requests/{request_id}",
    {
      params: { ...orgParams(), path: { request_id: params?.requestId ?? 0 } },
    },
    { enabled: params !== null, retry: retryUnlessForbidden },
  );

  return { valid: params !== null, query };
};

export const useAdminRequestGroup = () => {
  const params = useRouteParams(
    z.object({ groupId: z.coerce.number().int().positive() }),
  );
  const query = rqClient.useQuery(
    "get",
    "/api/admin/request-groups/{group_id}",
    {
      params: { ...orgParams(), path: { group_id: params?.groupId ?? 0 } },
    },
    { enabled: params !== null, retry: retryUnlessForbidden },
  );

  return { valid: params !== null, query };
};
