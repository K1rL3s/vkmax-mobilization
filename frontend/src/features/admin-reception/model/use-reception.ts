import { keepPreviousData } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

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

const houseFilterSchema = z.coerce
  .number()
  .int()
  .positive()
  .optional()
  .catch(undefined);

export const useOrgAppointments = (onDate: string) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const houseId = houseFilterSchema.parse(
    searchParams.get("house") ?? undefined,
  );
  const appointments = rqClient.useQuery(
    "get",
    "/api/admin/appointments",
    {
      params: { ...orgParams(), query: { on_date: onDate, house_id: houseId } },
    },
    { placeholderData: keepPreviousData },
  );
  const houses = rqClient.useQuery(
    "get",
    "/api/admin/houses",
    { params: { ...orgParams(), query: { limit: 100 } } },
    { enabled: houseId !== undefined },
  );

  return {
    appointments,
    houseId,
    houseAddress: houses.data?.items.find((house) => house.id === houseId)
      ?.address,
    clearHouse: () => setSearchParams({}, { replace: true }),
  };
};
