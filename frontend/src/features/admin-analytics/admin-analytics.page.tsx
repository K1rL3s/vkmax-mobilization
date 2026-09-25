import { useState } from "react";
import { Flex, Panel, Typography } from "@maxhub/max-ui";

import { chartIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import type { PeriodDays } from "./domain/period";
import { useChannels } from "./model/use-channels";
import { useDashboard } from "./model/use-dashboard";
import { useExecutors } from "./model/use-executors";
import { useMetersSeason } from "./model/use-meters-season";
import { BenchmarkLink } from "./ui/benchmark-link";
import { ChannelsSection } from "./ui/channels-section";
import { ChartsSection } from "./ui/charts-section";
import { ExecutorsSection } from "./ui/executors-section";
import { MetersSection } from "./ui/meters-section";
import { PeriodChips } from "./ui/period-chips";
import { TilesSection } from "./ui/tiles-section";

import styles from "./admin-analytics.module.css";

const AdminAnalyticsPage = () => {
  const [period, setPeriod] = useState<PeriodDays>(30);
  const dashboard = useDashboard(period);
  const meters = useMetersSeason();
  const channels = useChannels(period);
  const executors = useExecutors(period);

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text asChild variant="title" color="primary">
        <h1>Аналитика</h1>
      </Typography.Text>

      <PeriodChips value={period} onChange={setPeriod} />

      {dashboard.isPending && <LoadingState title="Считаем показатели" />}

      {dashboard.isError && <ErrorState onRetry={dashboard.retry} />}

      {!dashboard.isPending && !dashboard.isError && dashboard.isEmpty && (
        <EmptyState
          icon={chartIcon}
          title="За этот период заявок не было"
          description="Выберите период длиннее"
        />
      )}

      {!dashboard.isPending && !dashboard.isError && !dashboard.isEmpty && (
        <Flex direction="column" align="stretch" gapY={16}>
          <TilesSection
            now={dashboard.nowTiles}
            period={dashboard.periodTiles}
          />

          <ChartsSection charts={dashboard.charts} />
        </Flex>
      )}

      <MetersSection
        isPending={meters.isPending}
        isError={meters.isError}
        isEmpty={meters.isEmpty}
        onRetry={meters.retry}
        season={meters.season}
      />

      <ChannelsSection
        isPending={channels.isPending}
        isError={channels.isError}
        isEmpty={channels.isEmpty}
        onRetry={channels.retry}
        items={channels.items}
      />

      <ExecutorsSection
        isPending={executors.isPending}
        isError={executors.isError}
        isEmpty={executors.isEmpty}
        onRetry={executors.retry}
        items={executors.items}
      />

      <BenchmarkLink />
    </Panel>
  );
};

export const Component = AdminAnalyticsPage;
