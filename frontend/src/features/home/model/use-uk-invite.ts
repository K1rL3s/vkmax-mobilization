import type { HouseCard } from "@/features/house";
import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { plural } from "@/shared/lib/format";
import { haptic, shareToMax } from "@/shared/lib/max";

export const useUkInvite = (house: HouseCard, onSent: () => void) => {
  const params = { ...authParams(), path: { house_id: house.id } };
  const invite = rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/org-invite",
    { params },
    { enabled: house.org !== null },
  );
  const demand = rqClient.useMutation("post", "/api/houses/{house_id}/demand", {
    onSuccess: async () => {
      haptic.success();
      onSent();
      if (!house.org) {
        return;
      }
      const { data } = await invite.refetch();
      if (data) {
        shareToMax(data);
      }
    },
    onError: haptic.error,
  });
  const waiting = house.demand_count;
  const sent = invite.data;

  return {
    call: () => demand.mutate({ params }),
    isCalling: demand.isPending,
    error:
      demand.error &&
      errorMessage(demand.error, "Не получилось отправить. Попробуйте ещё раз"),
    status: `${house.org ? "Вы позвали УК." : "Вы с нами."} Подключения ${plural(waiting, ["ждёт", "ждут", "ждут"])} ${waiting} ${plural(waiting, ["житель", "жителя", "жителей"])}`,
    resend: sent ? () => shareToMax(sent) : null,
    inviteLink: sent?.link,
  };
};
