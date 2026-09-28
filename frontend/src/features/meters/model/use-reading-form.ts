import { useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { haptic, useClosingConfirmation } from "@/shared/lib/max";

import {
  anomalyOf,
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
  const [question, setQuestion] = useState<"anomaly" | "replace" | null>(null);

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
        haptic.success();
        await invalidatePaths("/api/flats/{flat_id}/meters");
        await invalidatePaths("/api/flats/{flat_id}/reading-periods");
      },
      onError: haptic.error,
    },
  );

  useClosingConfirmation(
    !submit.isSuccess &&
      (photos.photos.length > 0 ||
        Object.values(edited).some((value) => value.trim().length > 0)),
  );

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

  const nextMeter = readings.meters.find(
    (item) =>
      item.id !== meter?.id &&
      item.can_submit &&
      item.last_period !== selectedPeriod?.period,
  );

  const anomalies =
    meter && selectedPeriod
      ? zones.flatMap(
          (zone, index) =>
            anomalyOf(meter, selectedPeriod.period, zone, parsed[index]) ?? [],
        )
      : [];
  const replaced =
    meter?.last_period === selectedPeriod?.period ? meter?.last_values : null;

  const post = () => {
    setQuestion(null);

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
    openNext:
      nextMeter &&
      (() => {
        selectMeter(nextMeter.id);
        submit.reset();
      }),
    isSending: submit.isPending,
    error:
      submit.error &&
      errorMessage(
        submit.error,
        "Показания не ушли. Проверьте связь и попробуйте ещё раз",
      ),
    canSend:
      meter?.can_submit === true &&
      selectedPeriod !== undefined &&
      photos.photos.length > 0 &&
      !photos.isUploading &&
      parsed.every((value) => value !== null),
    send: () => {
      if (anomalies.length > 0) {
        setQuestion("anomaly");
      } else if (replaced) {
        setQuestion("replace");
      } else {
        post();
      }
    },
    question,
    anomalies,
    replaced,
    confirm: () => {
      if (question === "anomaly" && replaced) {
        setQuestion("replace");
      } else {
        post();
      }
    },
    dismissQuestion: () => setQuestion(null),
  };
};
