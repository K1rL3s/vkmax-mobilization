import { invalidatePaths } from "@/shared/api/query-client";

export const refreshRequests = () =>
  invalidatePaths(
    "/api/admin/requests",
    "/api/admin/requests/{request_id}",
    "/api/admin/request-groups/{group_id}",
    "/api/admin/executors",
  );
