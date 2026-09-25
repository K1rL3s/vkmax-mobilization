import { Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { StatusPill } from "@/shared/ui/status-pill";

import { formatMetric } from "../domain/metric";

type BenchmarkMetric = components["schemas"]["BenchmarkMetric"];

export const BenchmarkMetricRow = ({ metric }: { metric: BenchmarkMetric }) => {
  const { platform_median: median, rank, total } = metric;

  return (
    <Flex direction="column" align="stretch" gapY={4}>
      <Flex align="center" justify="space-between" gap={12}>
        <Typography.Text variant="detail" color="primary">
          {metric.label}
        </Typography.Text>

        <Typography.Text variant="body-strong" color="primary">
          {formatMetric(metric.value, metric.unit)}
        </Typography.Text>
      </Flex>

      {median === null || rank === null || total === null ? (
        <Typography.Text variant="detail" color="tertiary">
          Сравнение появится, когда данных наберётся больше
        </Typography.Text>
      ) : (
        <Flex align="center" gap={8} wrap="wrap">
          <Typography.Text variant="detail" color="secondary">
            медиана {formatMetric(median, metric.unit)}
          </Typography.Text>

          <StatusPill
            tone={rank <= Math.ceil(total / 3) ? "positive" : "neutral"}
          >
            {rank} место из {total}
          </StatusPill>
        </Flex>
      )}
    </Flex>
  );
};
