import { Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { EmptyState } from "@/shared/ui/state";

import { formatMetric } from "../domain/metric";
import type { PeriodDays } from "../domain/period";
import { useChannels } from "../model/use-channels";

import { FillBar } from "./fill-bar";
import { Section } from "./section";

const CHANNEL_LABEL: Record<components["schemas"]["RequestChannel"], string> = {
  miniapp: "Мини-апп",
  bot: "Бот",
  chat: "Чат дома",
  phone: "Звонок",
};

export const ChannelsSection = ({ period }: { period: PeriodDays }) => {
  const channels = useChannels(period);

  return (
    <Section
      title="Откуда приходят заявки"
      isPending={channels.isPending}
      isError={channels.isError}
      error={channels.error}
      onRetry={() => void channels.refetch()}
    >
      {channels.data?.is_empty ? (
        <EmptyState
          title="Заявок за период нет"
          description="Выберите период длиннее"
        />
      ) : (
        <Flex direction="column" align="stretch" gapY={10}>
          {channels.data?.items.map((item) => (
            <Flex
              key={item.channel}
              direction="column"
              align="stretch"
              gapY={4}
            >
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
};
