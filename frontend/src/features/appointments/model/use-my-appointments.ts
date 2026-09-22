import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { houseParams, useSession } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import type { Appointment, ReceptionSlot } from "../domain/schedule";

export const useMyAppointments = () => {
  const { currentResidency } = useSession();
  const confirm = useConfirm<Appointment>();

  // ручка отдаёт записи жителя по всем домам, в любом статусе и от поздних к
  // ранним, а прошедшая запись так и остаётся booked: экран открыт для одного
  // дома и показывает только предстоящие, ближайшую первой
  const list = rqClient.useQuery(
    "get",
    "/api/appointments",
    { params: houseParams() },
    {
      select: (data) =>
        data
          .filter(
            (item) =>
              item.status === "booked" &&
              item.house_id === currentResidency?.house_id &&
              Date.parse(item.starts_at) > Date.now(),
          )
          .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at)),
    },
  );

  const cancel = rqClient.useMutation(
    "delete",
    "/api/appointments/{appointment_id}",
    {
      onSuccess: async () => {
        confirm.dismiss();
        await Promise.all(
          ["/api/appointments", "/api/houses/{house_id}/reception-slots"].map(
            (path) =>
              queryClient.invalidateQueries({ queryKey: ["get", path] }),
          ),
        );
      },
    },
  );

  const items = list.data ?? [];
  const ownTimes = new Set(items.map((item) => Date.parse(item.starts_at)));

  return {
    items,
    // бэк отвечает на повторную запись тем же 409, что и на занятый слот, поэтому
    // своё время выключено заранее, а не объясняется после отказа
    isOwn: (slot: ReceptionSlot) => ownTimes.has(Date.parse(slot.starts_at)),
    isPending: list.isPending,
    isError: list.isError,
    retry: () => void list.refetch(),
    target: confirm.target,
    isOpen: confirm.isOpen,
    ask: (appointment: Appointment) => {
      cancel.reset();
      confirm.ask(appointment);
    },
    dismiss: () => {
      if (!cancel.isPending) {
        confirm.dismiss();
      }
    },
    isCancelling: cancel.isPending,
    isFailed: cancel.isError,
    confirm: () => {
      const target = confirm.target;

      if (target && !cancel.isPending) {
        cancel.mutate({
          params: { ...authParams(), path: { appointment_id: target.id } },
        });
      }
    },
  };
};
