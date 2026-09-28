import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

export type ChairmanHandover = components["schemas"]["ChairmanHandoverItem"];

const handoverParams = (houseId: number) => ({
  ...authParams(),
  path: { house_id: houseId },
});

export const useChairmanHandover = (houseId: number, enabled: boolean) =>
  rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/chairman-handover",
    { params: handoverParams(houseId) },
    { enabled },
  );

const refreshHandover = (houseId: number) =>
  queryClient.invalidateQueries({
    queryKey: rqClient.queryOptions(
      "get",
      "/api/houses/{house_id}/chairman-handover",
      { params: handoverParams(houseId) },
    ).queryKey,
  });

export const useIssueHandover = (houseId: number) =>
  rqClient.useMutation("post", "/api/houses/{house_id}/chairman-handover", {
    onSuccess: () => refreshHandover(houseId),
  });

export const useRevokeHandover = (houseId: number) =>
  rqClient.useMutation("delete", "/api/houses/{house_id}/chairman-handover", {
    onSuccess: () => refreshHandover(houseId),
  });
