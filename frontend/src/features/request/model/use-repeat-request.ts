import { generatePath, useNavigate } from "react-router-dom";

import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";

export const refetchRequests = async () => {
  await invalidatePaths("/api/requests/{request_id}");
  await invalidatePaths("/api/requests");
};

export const useRepeatRequest = () => {
  const navigate = useNavigate();

  return rqClient.useMutation("post", "/api/requests/{request_id}/repeat", {
    onSuccess: async (created) => {
      await refetchRequests();
      await navigate(
        generatePath(Routes.REQUEST, { requestId: String(created.id) }),
        { replace: true },
      );
    },
  });
};
