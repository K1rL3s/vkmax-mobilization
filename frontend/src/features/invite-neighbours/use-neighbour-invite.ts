import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { haptic, shareToMax } from "@/shared/lib/max";

export const useNeighbourInvite = (houseId: number | undefined) => {
  const params = { ...authParams(), path: { house_id: houseId ?? 0 } };
  const invite = rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/neighbour-invite",
    { params },
    { enabled: houseId !== undefined },
  );
  const leaflet = rqClient.useMutation(
    "post",
    "/api/houses/{house_id}/neighbour-invite/leaflet",
    { onSuccess: haptic.success, onError: haptic.error },
  );

  const share = () => {
    if (invite.data) {
      shareToMax({ text: invite.data.text, link: invite.data.link });
    }
  };

  return {
    invite,
    subtitle: invite.data?.is_connected
      ? "Покажите QR или отправьте ссылку в чат подъезда. Дом уже будет выбран, квартиру сосед укажет сам"
      : "УК этого дома ещё нет в Жэке. Чем больше соседей её позовут, тем заметнее дом для управляющих компаний",
    share,
    sendLeaflet: () => leaflet.mutate({ params }),
    isSendingLeaflet: leaflet.isPending,
    isLeafletSent: leaflet.isSuccess,
    leafletLabel: leaflet.isSuccess
      ? "Листовка в чате с ботом"
      : "Получить листовку в чат с ботом",
    leafletError:
      leaflet.error &&
      errorMessage(
        leaflet.error,
        "Не получилось отправить. Проверьте связь и попробуйте ещё раз",
      ),
  };
};
