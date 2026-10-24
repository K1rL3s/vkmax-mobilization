import type { components } from "@/shared/api/schema/generated";
import { EmptyState } from "@/shared/ui/state";

import type { PeriodDays } from "../domain/period";
import { useChannels } from "../model/use-channels";

import { Section } from "./section";
import { SplitRows } from "./split-rows";

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
        <SplitRows
          rows={(channels.data?.items ?? []).map((item) => ({
            key: item.channel,
            label: CHANNEL_LABEL[item.channel],
            count: item.count,
            share: item.share,
          }))}
        />
      )}
    </Section>
  );
};
