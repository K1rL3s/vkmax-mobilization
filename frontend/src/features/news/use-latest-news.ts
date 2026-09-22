import { rqClient } from "@/shared/api/instance";
import { houseParams } from "@/shared/model/session";

export const useLatestNews = () =>
  rqClient.useQuery("get", "/api/announcements", {
    params: { ...houseParams(), query: { limit: 3 } },
  });
