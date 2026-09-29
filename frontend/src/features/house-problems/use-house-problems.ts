import { rqClient } from "@/shared/api/instance";
import { houseParams } from "@/shared/model/session";

export const useHouseProblems = () =>
  rqClient.useQuery("get", "/api/requests/house-problems", {
    params: houseParams(),
  });
