import { authParams, rqClient } from "@/shared/api/instance";

export const useRequestCategories = () =>
  rqClient.useQuery(
    "get",
    "/api/request-categories",
    { params: authParams() },
    { staleTime: Infinity },
  );
