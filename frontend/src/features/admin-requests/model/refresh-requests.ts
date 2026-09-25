import { queryClient } from "@/shared/api/query-client";

export const refreshRequests = () =>
  Promise.all(
    [
      "/api/admin/requests",
      "/api/admin/requests/{request_id}",
      "/api/admin/request-groups/{group_id}",
      "/api/admin/executors",
    ].map((path) => queryClient.invalidateQueries({ queryKey: ["get", path] })),
  );
