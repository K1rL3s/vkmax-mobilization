import { keepPreviousData } from "@tanstack/react-query";

import { rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { orgParams, useSession } from "@/shared/model/session";

// часы приёма читает и пишет только администратор организации, и список
// квартир для сбора доступа требует тех же прав. Роль известна из сессии,
// поэтому у сотрудника без прав запроса нет вовсе: гарантированный 403
// превратился бы в состояние ошибки, которое ничего не объясняет
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

// слоты приёма житель читает из тех же окон, поэтому его кэш тоже устарел
export const useSaveReceptionWindows = () =>
  rqClient.useMutation("put", "/api/admin/reception/windows", {
    onSuccess: () =>
      Promise.all(
        [
          "/api/admin/reception/windows",
          "/api/houses/{house_id}/reception-slots",
        ].map((path) =>
          queryClient.invalidateQueries({ queryKey: ["get", path] }),
        ),
      ),
  });

// переключение дня держит предыдущий список: иначе каждая стрелка роняет
// экран в спиннер, хотя данные меняются на несколько строк
export const useOrgAppointments = (onDate: string) =>
  rqClient.useQuery(
    "get",
    "/api/admin/appointments",
    { params: { ...orgParams(), query: { on_date: onDate } } },
    { placeholderData: keepPreviousData },
  );
