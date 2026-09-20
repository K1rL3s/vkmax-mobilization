import { useState } from "react";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

import {
  formatReading,
  parseReading,
  zonesOf,
  type TariffZone,
} from "../domain/reading";

import { useFlatReadings } from "./use-flat-readings";
import { useReadingPhotos } from "./use-reading-photos";

export const useReadingForm = () => {
  const readings = useFlatReadings();
  const [meterId, setMeterId] = useState<number | null>(null);
  const [period, setPeriod] = useState<string | null>(null);
  const [edited, setEdited] = useState<Partial<Record<TariffZone, string>>>({});

  // выбор по умолчанию выводится из данных, а не ставится эффектом: списки
  // приходят после первого рендера, и эффект дал бы лишний кадр с пустой формой
  const meter =
    readings.meters.find((item) => item.id === meterId) ??
    readings.meters.find((item) => item.can_submit) ??
    readings.meters.at(0);
  const openPeriods = readings.periods.filter((item) => item.is_open);
  const selectedPeriod =
    openPeriods.find((item) => item.period === period) ?? openPeriods.at(0);

  const photos = useReadingPhotos(meter?.type);
  const zones = meter ? zonesOf(meter) : [];

  const submit = rqClient.useMutation(
    "post",
    "/api/meters/{meter_id}/readings",
    {
      onSuccess: async () => {
        // подача меняет и последнее показание счётчика, и отметку периода
        await queryClient.invalidateQueries({
          queryKey: ["get", "/api/flats/{flat_id}/meters"],
        });
        await queryClient.invalidateQueries({
          queryKey: ["get", "/api/flats/{flat_id}/reading-periods"],
        });
      },
    },
  );

  // распознанное показание живёт в поле до первой правки жителя, поэтому
  // значение поля - это правка поверх подсказки, а не отдельное состояние
  const valueOf = (zone: TariffZone) => {
    const suggested = photos.recognized?.[zone];

    return (
      edited[zone] ?? (suggested === undefined ? "" : formatReading(suggested))
    );
  };

  const parsed = zones.map((zone) => parseReading(valueOf(zone)));

  const selectMeter = (next: number) => {
    setMeterId(next);
    setEdited({});
    photos.reset();
  };

  const send = () => {
    if (!meter || !selectedPeriod || parsed.some((value) => value === null)) {
      return;
    }

    const values = Object.fromEntries(
      zones.map((zone, index) => [zone, parsed[index]]),
    ) as Record<TariffZone, number>;
    const recognized = photos.recognized;

    submit.mutate({
      params: { ...authParams(), path: { meter_id: meter.id } },
      body: {
        period: selectedPeriod.period,
        values,
        photos: photos.names,
        ocr_used: recognized !== null,
        // принятым распознавание считается, только если житель отправил ровно
        // те значения, которые подставило фото
        ocr_accepted:
          recognized !== null &&
          zones.every((zone) => recognized[zone] === values[zone]),
      },
    });
  };

  return {
    ...readings,
    meter,
    selectMeter,
    periods: openPeriods,
    period: selectedPeriod,
    selectPeriod: setPeriod,
    zones,
    valueOf,
    setValue: (zone: TariffZone, value: string) =>
      setEdited((current) => ({ ...current, [zone]: value })),
    photos,
    result: submit.data,
    resubmit: submit.reset,
    isSending: submit.isPending,
    isFailed: submit.isError,
    canSend:
      meter?.can_submit === true &&
      selectedPeriod !== undefined &&
      photos.photos.length > 0 &&
      parsed.every((value) => value !== null),
    send,
  };
};
