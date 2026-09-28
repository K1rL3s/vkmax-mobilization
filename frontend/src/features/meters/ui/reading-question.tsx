import { ConfirmDialog } from "@/shared/ui/confirm-dialog";

import {
  formatPeriod,
  formatReading,
  METER_UNIT,
  monthlyLimit,
  parseReading,
  ZONE_LABEL,
  type Anomaly,
  type Meter,
  type TariffZone,
} from "../domain/reading";

type ReadingQuestionProps = {
  meter: Meter;
  period: string;
  zones: TariffZone[];
  question: "anomaly" | "replace" | null;
  anomalies: Anomaly[];
  replaced: Partial<Record<TariffZone, number>> | null | undefined;
  valueOf: (zone: TariffZone) => string;
  onConfirm: () => void;
  onClose: () => void;
};

export const ReadingQuestion = ({
  meter,
  period,
  zones,
  question,
  anomalies,
  replaced,
  valueOf,
  onConfirm,
  onClose,
}: ReadingQuestionProps) => {
  const unit = METER_UNIT[meter.type];
  const was = (zone: TariffZone) =>
    zones.length > 1 ? `${ZONE_LABEL[zone]}: было` : "Было";
  const listOf = (text: (zone: TariffZone) => string) =>
    zones
      .map((zone) =>
        zones.length > 1
          ? `${ZONE_LABEL[zone].toLowerCase()} ${text(zone)}`
          : text(zone),
      )
      .join(", ");
  const reason = (anomaly: Anomaly) =>
    anomaly.kind === "below"
      ? "Счётчик не крутится назад - проверьте цифры."
      : `Обычно за месяц уходит до ${monthlyLimit(meter).toLocaleString("ru-RU")} ${unit} - проверьте запятую.`;

  const isAnomaly = question === "anomaly";

  return (
    <ConfirmDialog
      isOpen={question !== null}
      title={isAnomaly ? "Проверьте показание" : "Заменить показания?"}
      description={
        isAnomaly
          ? anomalies
              .map(
                (anomaly) =>
                  `${was(anomaly.zone)} ${formatReading(anomaly.previous)}, сейчас ${formatReading(anomaly.current)} ${unit}. ${reason(anomaly)}`,
              )
              .join(" ")
          : `За ${formatPeriod(period)} уже передано ${listOf((zone) =>
              formatReading(replaced?.[zone] ?? 0),
            )} ${unit}. Заменить на ${listOf((zone) =>
              formatReading(parseReading(valueOf(zone)) ?? 0),
            )}?`
      }
      confirmLabel={isAnomaly ? "Отправить как есть" : "Заменить"}
      confirmVariant={isAnomaly ? "primary" : "destructive"}
      onConfirm={onConfirm}
      onClose={onClose}
    />
  );
};
