import { useLocation, useNavigate } from "react-router-dom";

import { useHouseCard } from "@/features/house";
import { authParams, rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import { houseParams } from "@/shared/model/session";
import { useConfirm } from "@/shared/ui/confirm-dialog";

import { createSchedule, deviceTimeZone } from "../domain/schedule";
import { refetchAppointments } from "./use-my-appointments";

export const useAppointment = (appointmentId: number) => {
  const navigate = useNavigate();
  const { key } = useLocation();
  const confirm = useConfirm();

  const list = rqClient.useQuery(
    "get",
    "/api/appointments",
    { params: houseParams() },
    { select: (data) => data.find((item) => item.id === appointmentId) },
  );

  const appointment = list.data;
  const house = useHouseCard(appointment?.house_id);
  const org = house.data?.org ?? null;

  const cancel = rqClient.useMutation(
    "delete",
    "/api/appointments/{appointment_id}",
    {
      onSuccess: async () => {
        confirm.dismiss();
        await refetchAppointments();

        if (key === "default") {
          void navigate(Routes.APPOINTMENTS, { replace: true });
          return;
        }

        void navigate(-1);
      },
    },
  );

  return {
    appointment,
    org,
    schedule: createSchedule(org?.timezone ?? deviceTimeZone()),
    isPending: list.isPending || (appointment !== undefined && house.isPending),
    isError: list.isError || house.isError,
    loadError: list.error ?? house.error,
    retry: () => {
      if (list.isError) {
        void list.refetch();
      }

      if (house.isError) {
        void house.refetch();
      }
    },
    isOpen: confirm.isOpen,
    ask: () => {
      cancel.reset();
      confirm.ask();
    },
    dismiss: () => {
      if (!cancel.isPending) {
        confirm.dismiss();
      }
    },
    isCancelling: cancel.isPending,
    isFailed: cancel.isError,
    confirm: () => {
      if (!cancel.isPending) {
        cancel.mutate({
          params: {
            ...authParams(),
            path: { appointment_id: appointmentId },
          },
        });
      }
    },
  };
};
