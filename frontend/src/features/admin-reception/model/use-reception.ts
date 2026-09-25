import { keepPreviousData } from "@tanstack/react-query";

import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { orgParams, useSession } from "@/shared/model/session";

export const useIsOrgAdmin = (): boolean => {
  const { currentOrg } = useSession();

  return currentOrg?.role === "creator" || currentOrg?.role === "admin";
};

export const useReceptionWindows = (enabled: boolean) =>
  rqClient.useQuery(
    "get",
    "/api/admin/reception/windows",
    { params: orgParams() },
    { enabled },
  );

export const useSaveReceptionWindows = () =>
  rqClient.useMutation("put", "/api/admin/reception/windows", {
    onSuccess: () =>
      invalidatePaths(
        "/api/admin/reception/windows",
        "/api/houses/{house_id}/reception-slots",
      ),
  });

export const useOrgAppointments = (onDate: string) =>
  rqClient.useQuery(
    "get",
    "/api/admin/appointments",
    { params: { ...orgParams(), query: { on_date: onDate } } },
    { placeholderData: keepPreviousData },
  );
