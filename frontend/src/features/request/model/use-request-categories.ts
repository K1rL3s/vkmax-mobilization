import { authParams, rqClient } from "@/shared/api/instance";

// справочник категорий меняется раз в релиз: держим его в кеше и не ходим за
// ним повторно ни из карточки, ни из мастера
export const useRequestCategories = () =>
  rqClient.useQuery(
    "get",
    "/api/request-categories",
    { params: authParams() },
    { staleTime: Infinity },
  );
