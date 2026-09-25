import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { formatArea, formatPercent } from "@/shared/lib/format";

import { flatsCount, weightlessLine, type PollResults } from "../domain/poll";

import styles from "./quorum-panel.module.css";

export const QuorumPanel = ({ results }: { results: PollResults }) => {
  const reached = results.quorum_reached;
  const left = results.quorum_percent - results.voted_area_percent;

  return (
    <div className={styles.Panel}>
      <Flex align="center" gap={8}>
        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          Кворум по площади
        </Typography.Text>

        <Typography.Text
          className={cn(styles.Value, reached && styles.reached)}
          variant="body-strong"
        >
          {formatPercent(results.voted_area_percent)}
        </Typography.Text>
      </Flex>

      <div className={styles.Track}>
        <div
          className={cn(styles.Fill, reached && styles.reached)}
          style={{
            width: `${Math.min(results.voted_area_percent / 100, 100)}%`,
          }}
        />
        <div
          className={styles.Mark}
          style={{ left: `${Math.min(results.quorum_percent / 100, 100)}%` }}
        />
      </div>

      <Typography.Text variant="description" color="secondary">
        Проголосовали {results.voted_flats} из {flatsCount(results.total_flats)}{" "}
        · {formatArea(results.voted_area)} из {formatArea(results.total_area)}
      </Typography.Text>

      <Typography.Text
        className={cn(reached && styles.reached)}
        variant="description"
        color={reached ? undefined : "secondary"}
      >
        {reached
          ? `Кворум набран: порог ${formatPercent(results.quorum_percent)} площади дома`
          : `До кворума не хватает ${formatPercent(left)} площади дома`}
      </Typography.Text>

      {results.flats_without_area > 0 && (
        <Typography.Text variant="description" color="secondary">
          Вне расчёта {flatsCount(results.flats_without_area)} без указанной
          площади
        </Typography.Text>
      )}

      {results.unverified_flats > 0 && (
        <Typography.Text variant="description" color="secondary">
          {weightlessLine(results.unverified_flats)}
        </Typography.Text>
      )}
    </div>
  );
};
