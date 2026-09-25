import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";

export const useOrgHouses = (enabled: boolean) =>
  rqClient.useQuery(
    "get",
    "/api/admin/houses",
    { params: { ...orgParams(), query: { limit: 100 } } },
    { enabled },
  );

export const useOrgAccessRequests = () =>
  rqClient.useQuery("get", "/api/admin/access-requests", {
    params: orgParams(),
  });

const paramsSchema = z.object({
  accessRequestId: z.coerce.number().int().positive(),
});

export const useAccessRequest = () => {
  const route = useRouteParams(paramsSchema);

  const query = rqClient.useQuery(
    "get",
    "/api/admin/access-requests/{access_request_id}",
    {
      params: {
        ...orgParams(),
        path: { access_request_id: route?.accessRequestId ?? 0 },
      },
    },
    { enabled: route !== null },
  );

  return { valid: route !== null, query };
};

const withoutCellSchema = z.object({ withoutCell: z.array(z.string()) });

export const useWithoutCell = () => {
  const { state, pathname } = useLocation();
  const navigate = useNavigate();
  const [flats] = useState(
    () => withoutCellSchema.safeParse(state).data?.withoutCell ?? [],
  );

  useEffect(() => {
    if (state !== null) {
      void navigate(pathname, { replace: true, state: null });
    }
  }, [state, pathname, navigate]);

  return flats;
};
