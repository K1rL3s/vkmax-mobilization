import { Button, Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { EmptyState } from "@/shared/ui/state";

import { periodTitle, windowTitle } from "../domain/meters";
import { formatMetric } from "../domain/metric";
import { useMetersSeason } from "../model/use-meters-season";
import { useRemind } from "../model/use-remind";

import { FillBar } from "./fill-bar";
import { Section } from "./section";
import styles from "./meters-section.module.css";

type MetersSeason = components["schemas"]["MetersSeasonResponse"];

const Remind = ({ season }: { season: MetersSeason }) => {
  const remind = useRemind();

  if (remind.queued !== null) {
    return (
      <Typography.Text variant="detail" color="secondary">
        {remind.queued > 0
          ? `Напомнили ${remind.queued} жителям`
          : "Сегодня уже напоминали, следующее напоминание - завтра"}
      </Typography.Text>
    );
  }

  return (
    <Flex direction="column" align="flex-start" gapY={6}>
      <Button
        size="medium"
        variant="secondary"
        disabled={!season.window_open || remind.isPending}
        onClick={remind.remind}
      >
        Напомнить не сдавшим
      </Button>

      {!season.window_open && (
        <Typography.Text variant="detail" color="tertiary">
          Приём показаний закрыт, напоминание уходит{" "}
          {windowTitle(season.window_from, season.window_to)}
        </Typography.Text>
      )}

      {remind.error && (
        <Typography.Text className={styles.Failure} variant="detail">
          {remind.error}
        </Typography.Text>
      )}
    </Flex>
  );
};

export const MetersSection = () => {
  const meters = useMetersSeason();
  const season = meters.data;

  return (
    <Section
      title="Показания"
      note={season ? `за ${periodTitle(season.period)}` : undefined}
      isPending={meters.isPending}
      isError={meters.isError}
      onRetry={() => void meters.refetch()}
    >
      {season === undefined || season.is_empty ? (
        <EmptyState
          title="В домах организации нет квартир с показаниями"
          description="Показания появятся, когда жители подтвердят квартиры и заведут счётчики"
        />
      ) : (
        <Flex direction="column" align="stretch" gapY={12}>
          <Typography.Text variant="header" color="primary">
            Сдано {season.submitted} из{" "}
            {season.submitted + season.not_submitted}
          </Typography.Text>

          <Flex direction="column" align="stretch" gapY={10}>
            {season.houses.map((house) => (
              <Flex
                key={house.house_id}
                direction="column"
                align="stretch"
                gapY={4}
              >
                <Typography.Text variant="detail" color="primary">
                  {house.address}
                </Typography.Text>

                <Flex align="center" justify="space-between" gap={8}>
                  <Typography.Text variant="detail" color="secondary">
                    {house.submitted} из {house.flats_total}
                  </Typography.Text>

                  <Typography.Text variant="detail-strong" color="primary">
                    {formatMetric(house.percent, "percent")}
                  </Typography.Text>
                </Flex>

                <FillBar share={house.percent} />
              </Flex>
            ))}
          </Flex>

          <Remind season={season} />
        </Flex>
      )}
    </Section>
  );
};
