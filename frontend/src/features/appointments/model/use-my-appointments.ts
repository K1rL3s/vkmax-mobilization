import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { houseParams, useSession } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import type { Appointment, ReceptionSlot } from "../domain/schedule";

export const useMyAppointments = () => {
  const { currentResidency } = useSession();
  const confirm = useConfirm<Appointment>();

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
        await refetchAppointments();
      },
    },
  );

  const items = list.data ?? [];
  const ownTimes = new Set(items.map((item) => Date.parse(item.starts_at)));

  return {
    items,
    isOwn: (slot: ReceptionSlot) => ownTimes.has(Date.parse(slot.starts_at)),
    isPending: list.isPending,
    isError: list.isError,
    loadError: list.error,
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

export const refetchAppointments = () =>
  invalidatePaths(
    "/api/appointments",
    "/api/houses/{house_id}/reception-slots",
  );
