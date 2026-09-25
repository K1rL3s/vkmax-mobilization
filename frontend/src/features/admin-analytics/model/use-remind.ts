import { errorDetail } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { orgParams } from "@/shared/model/session";

export const useRemind = () => {
  const remind = rqClient.useMutation(
    "post",
    "/api/admin/analytics/meters-season/remind",
  );

  return {
    isPending: remind.isPending,
    queued: remind.isSuccess ? remind.data.queued : null,
    error: remind.isError
      ? (errorDetail(remind.error) ?? "Не получилось отправить напоминание")
      : null,
    remind: () =>
      remind.mutate({ params: orgParams(), body: { house_ids: [] } }),
  };
};
