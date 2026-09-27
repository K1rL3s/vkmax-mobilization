import { Button, Flex, Switch, Typography } from "@maxhub/max-ui";

import { formatPeriod, METER_LABEL } from "@/features/meters";
import { formatDay } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";
import { meterIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import {
  type Reading,
  readingConsumption,
  readingValue,
} from "../domain/reading";
import { useHouseReadings } from "../model/use-house-readings";

import styles from "./readings-section.module.css";

const ReadingRow = ({ reading }: { reading: Reading }) => (
  <Card className={styles.Row}>
    <Flex align="center" gap={8}>
      <Typography.Text
        className={styles.Grow}
        variant="body-strong"
        color="primary"
      >
        Кв. {reading.flat_number} · {METER_LABEL[reading.meter_type]}
      </Typography.Text>

      {reading.is_below_previous && (
        <StatusPill tone="negative">Меньше прошлого</StatusPill>
      )}
    </Flex>

    <Typography.Text variant="body" color="primary">
      {readingValue(reading)}
    </Typography.Text>

    <Typography.Text variant="description" color="secondary">
      {formatPeriod(reading.period)}, {readingConsumption(reading)}
      {reading.ocr_used && ", по фото"}
    </Typography.Text>

    <Typography.Text variant="description" color="secondary">
      {reading.submitted_by_name} · {formatDay(reading.submitted_at)} · счётчик{" "}
      {reading.serial}
    </Typography.Text>
  </Card>
);

export const ReadingsSection = ({ houseId }: { houseId: number }) => {
  const readings = useHouseReadings(houseId);

  const content = () => {
    if (readings.isPending) {
      return <LoadingState title="Загружаем показания" />;
    }

    if (readings.isError) {
      return (
        <ErrorState
          error={readings.loadError}
          description="Не получилось загрузить показания. Проверьте связь и попробуйте ещё раз"
          onRetry={readings.retry}
        />
      );
    }

    if (readings.items.length === 0) {
      return readings.onlyBelow ? (
        <EmptyState
          icon={meterIcon}
          title="Подозрительных показаний нет"
          description="Никто не подал показание меньше предыдущего"
        />
      ) : (
        <EmptyState
          icon={meterIcon}
          title="Показаний пока нет"
          description="Жители подают показания в окно, которое задаётся в настройках организации"
        />
      );
    }

    return (
      <>
        {readings.items.map((reading) => (
          <ReadingRow key={reading.id} reading={reading} />
        ))}

        {readings.hasMore && (
          <Button
            size="medium"
            variant="secondary"
            loading={readings.isLoadingMore}
            onClick={readings.loadMore}
          >
            Показать ещё
          </Button>
        )}
      </>
    );
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2 className={styles.Title}>Показания</h2>
        </Typography.Text>

        <Flex asChild align="center" gap={12}>
          <label className={styles.Toggle}>
            <Flex
              className={styles.Grow}
              align="stretch"
              direction="column"
              gapY={2}
            >
              <Typography.Text variant="body" color="primary">
                Только меньше прошлых
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                Ошибка при вводе или замена счётчика
              </Typography.Text>
            </Flex>

            <Switch
              checked={readings.onlyBelow}
              onChange={(event) => readings.setOnlyBelow(event.target.checked)}
            />
          </label>
        </Flex>

        {content()}
      </section>
    </Flex>
  );
};
