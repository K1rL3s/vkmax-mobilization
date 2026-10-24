import { Flex, Typography } from "@maxhub/max-ui";

import { formatMetric } from "../domain/metric";

import { FillBar } from "./fill-bar";

export const SplitRows = ({
  rows,
}: {
  rows: { key: string; label: string; count: number; share: number }[];
}) => (
  <Flex direction="column" align="stretch" gapY={12}>
    {rows.map((row) => (
      <Flex key={row.key} direction="column" align="stretch" gapY={4}>
        <Flex align="center" justify="space-between" gap={8}>
          <Typography.Text variant="detail" color="primary">
            {row.label}
          </Typography.Text>

          <Typography.Text variant="detail" color="secondary">
            {row.count} · {formatMetric(row.share, "percent")}
          </Typography.Text>
        </Flex>

        <FillBar share={row.share} />
      </Flex>
    ))}
  </Flex>
);
