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
    // числа сезона напоминание не меняет, и мигание загрузкой прочиталось бы
    // как пересчёт, поэтому запроса за ними после успеха нет
    queued: remind.isSuccess ? remind.data.queued : null,
    error: remind.isError
      ? (errorDetail(remind.error) ?? "Не получилось отправить напоминание")
      : null,
    remind: () => {
      if (remind.isPending) {
        return;
      }

      // пустой house_ids - вся организация: дома в запросе не перечисляются
      remind.mutate({ params: orgParams(), body: { house_ids: [] } });
    },
  };
};
