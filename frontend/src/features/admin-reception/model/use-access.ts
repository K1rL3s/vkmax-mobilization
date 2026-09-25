import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";

// дом сбора выбирается из домов организации; своя копия запроса, а не общий
// хук: два потребителя - это ещё не повод заводить общее место. Сотруднику
// без прав форма недоступна, и запроса за домами для неё тоже нет
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

  return rqClient.useQuery(
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
};

const withoutCellSchema = z.object({ withoutCell: z.array(z.string()) });

export const withoutCellState = (withoutCell: string[]) => ({ withoutCell });

// квартиры без ячейки бэк отдаёт только в ответе на создание, поэтому на
// карточку они приезжают состоянием навигации. Состояние переживает
// перезагрузку и возврат назад: читаем один раз и сразу стираем из истории
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
