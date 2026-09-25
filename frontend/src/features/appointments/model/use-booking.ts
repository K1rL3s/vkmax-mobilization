import { useState } from "react";

import { useHouseCard } from "@/features/house";
import { isFinished } from "@/features/request";
import { isConflict } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { houseParams, useSession } from "@/shared/model/session";

import { createSchedule, deviceTimeZone } from "../domain/schedule";
import { refetchAppointments } from "./use-my-appointments";

export const useBooking = () => {
  const { currentResidency } = useSession();
  const houseId = currentResidency?.house_id;

  const house = useHouseCard(houseId);

  const slots = rqClient.useQuery(
    "get",
    "/api/houses/{house_id}/reception-slots",
    { params: { ...authParams(), path: { house_id: houseId ?? 0 } } },
    { enabled: houseId !== undefined },
  );

  const requests = rqClient.useQuery("get", "/api/requests", {
    params: { ...houseParams(), query: { limit: 100 } },
  });

  const [chosenDay, setChosenDay] = useState<string | null>(null);
  const [chosenSlot, setChosenSlot] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<number | null>(null);

  const schedule = createSchedule(
    house.data?.org?.timezone ?? deviceTimeZone(),
  );
  const days = schedule.receptionDays(slots.data ?? []);
  const day =
    days.find((item) => item.key === chosenDay) ??
    days.find((item) => item.slots.some((slot) => slot.is_free)) ??
    days.find((item) => item.slots.length > 0);
  const slot = day?.slots.find(
    (item) => item.starts_at === chosenSlot && item.is_free,
  );

  const openRequests = (requests.data?.items ?? []).filter(
    (item) => !isFinished(item.status),
  );

  const book = rqClient.useMutation("post", "/api/appointments", {
    onSuccess: async () => {
      setChosenSlot(null);
      setRequestId(null);
      await refetchAppointments();
    },
    onError: async (error) => {
      if (isConflict(error)) {
        setChosenSlot(null);
        await slots.refetch();
      }
    },
  });

  const queries = [house, slots, requests];

  return {
    org: house.data?.org ?? null,
    schedule,
    isPending: queries.some((query) => query.isPending),
    isError: queries.some((query) => query.isError),
    retry: () => {
      for (const query of queries) {
        if (query.isError) {
          void query.refetch();
        }
      }
    },
    days,
    day,
    selectDay: (key: string) => {
      setChosenDay(key);
      setChosenSlot(null);
      book.reset();
    },
    slot,
    selectSlot: (startsAt: string) => {
      setChosenSlot(startsAt);
      book.reset();
    },
    openRequests,
    requestId,
    selectRequest: setRequestId,
    isSending: book.isPending,
    error:
      book.isError &&
      (isConflict(book.error)
        ? "Это время только что заняли, выберите другое"
        : "Не получилось записаться. Проверьте связь и попробуйте ещё раз"),
    booked: book.data,
    bookedRequest: openRequests.find(
      (item) => item.id === book.data?.request_id,
    ),
    finish: book.reset,
    send: () => {
      if (slot && !book.isPending) {
        book.mutate({
          params: houseParams(),
          body: { starts_at: slot.starts_at, request_id: requestId },
        });
      }
    },
  };
};
