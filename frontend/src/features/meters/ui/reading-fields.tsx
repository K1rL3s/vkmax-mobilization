import { Flex, Input, Typography } from "@maxhub/max-ui";

import { Icon, alertIcon } from "@/shared/ui/icon";

import {
  formatReading,
  parseReading,
  ZONE_LABEL,
  type Meter,
  type TariffZone,
} from "../domain/reading";

import styles from "./reading-fields.module.css";

type ReadingFieldsProps = {
  meter: Meter;
  zones: TariffZone[];
  valueOf: (zone: TariffZone) => string;
  onChange: (zone: TariffZone, value: string) => void;
};

export const ReadingFields = ({
  meter,
  zones,
  valueOf,
  onChange,
}: ReadingFieldsProps) => {
  return (
    <Flex direction="column" align="stretch" gap={16}>
      {zones.map((zone) => {
        const previous = meter.last_values?.[zone];
        const current = parseReading(valueOf(zone));
        const isBelow =
          previous !== undefined && current !== null && current < previous;

        return (
          <Flex key={zone} direction="column" align="stretch" gap={8}>
            <Typography.Text asChild variant="detail-strong" color="primary">
              <label htmlFor={`reading-${zone}`}>{ZONE_LABEL[zone]}</label>
            </Typography.Text>

            <Input
              id={`reading-${zone}`}
              inputMode="decimal"
              placeholder="0"
              value={valueOf(zone)}
              hint={
                previous === undefined
                  ? "Первое показание счётчика"
                  : `Прошлое: ${formatReading(previous)}`
              }
              onChange={(event) => onChange(zone, event.target.value)}
            />

            {isBelow && (
              <Flex align="center" gap={8}>
                <Icon src={alertIcon} size={20} className={styles.Alert} />
                <Typography.Text
                  variant="description"
                  color="primary"
                  className={styles.Warning}
                >
                  Меньше прошлого показания. Проверьте — отправить всё равно
                  можно
                </Typography.Text>
              </Flex>
            )}
          </Flex>
        );
      })}
    </Flex>
  );
};
