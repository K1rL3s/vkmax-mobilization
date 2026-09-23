import { Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { EmptyState } from "@/shared/ui/state";

import { CHANNEL_LABEL } from "../domain/channel";
import { formatMetric } from "../domain/metric";

import { FillBar } from "./fill-bar";
import { Section } from "./section";

type ChannelsSectionProps = {
  isPending: boolean;
  isError: boolean;
  isEmpty: boolean;
  onRetry: () => void;
  items: components["schemas"]["ChannelSplitItem"][];
};

export const ChannelsSection = ({
  isPending,
  isError,
  isEmpty,
  onRetry,
  items,
}: ChannelsSectionProps) => (
  <Section
    title="Откуда приходят заявки"
    isPending={isPending}
    isError={isError}
    onRetry={onRetry}
  >
    {isEmpty ? (
      <EmptyState
        title="Заявок за период нет"
        description="Выберите период длиннее"
      />
    ) : (
      <Flex direction="column" align="stretch" gapY={10}>
        {items.map((item) => (
          <Flex key={item.channel} direction="column" align="stretch" gapY={4}>
            <Flex align="center" justify="space-between" gap={8}>
              <Typography.Text variant="detail" color="primary">
                {CHANNEL_LABEL[item.channel]}
              </Typography.Text>

              <Typography.Text variant="detail" color="secondary">
                {item.count} · {formatMetric(item.share, "percent")}
              </Typography.Text>
            </Flex>

            <FillBar share={item.share} />
          </Flex>
        ))}
      </Flex>
    )}
  </Section>
);
