import { Flex, Input, Typography } from "@maxhub/max-ui";

import { Icon, alertIcon } from "@/shared/ui/icon";

import {
  baselineOf,
  formatReading,
  isImplausiblyHigh,
  parseReading,
  ZONE_LABEL,
  type Meter,
  type TariffZone,
} from "../domain/reading";

import styles from "./reading-fields.module.css";

type ReadingFieldsProps = {
  meter: Meter;
  period: string;
  zones: TariffZone[];
  valueOf: (zone: TariffZone) => string;
  onChange: (zone: TariffZone, value: string) => void;
};

export const ReadingFields = ({
  meter,
  period,
  zones,
  valueOf,
  onChange,
}: ReadingFieldsProps) => {
  return (
    <Flex direction="column" align="stretch" gap={16}>
      {zones.map((zone) => {
        const previous = baselineOf(meter, period).values?.[zone];
        const current = parseReading(valueOf(zone));
        const isBelow =
          previous !== undefined && current !== null && current < previous;
        const isHigh =
          previous !== undefined &&
          current !== null &&
          isImplausiblyHigh(meter, period, current - previous);

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
                  Меньше прошлого показания. Проверьте цифры: расход и сумму с
                  таким значением не посчитаем. Отправить всё равно можно
                </Typography.Text>
              </Flex>
            )}

            {isHigh && (
              <Flex align="center" gap={8}>
                <Icon src={alertIcon} size={20} className={styles.Alert} />
                <Typography.Text
                  variant="description"
                  color="primary"
                  className={styles.Warning}
                >
                  Расход в разы больше обычного для квартиры. Проверьте цифры и
                  запятую. Отправить всё равно можно
                </Typography.Text>
              </Flex>
            )}
          </Flex>
        );
      })}
    </Flex>
  );
};
