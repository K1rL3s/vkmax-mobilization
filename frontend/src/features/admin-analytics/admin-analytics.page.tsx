import { useState } from "react";
import { Flex, Panel, Typography } from "@maxhub/max-ui";

import { chartIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import type { PeriodDays } from "./domain/period";
import { useDashboard } from "./model/use-dashboard";
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

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text asChild variant="header" color="primary">
        <h1>Аналитика</h1>
      </Typography.Text>

      <PeriodChips value={period} onChange={setPeriod} />

      {dashboard.isPending && <LoadingState title="Считаем показатели" />}

      {dashboard.isError && (
        <ErrorState
          error={dashboard.error}
          onRetry={() => void dashboard.refetch()}
        />
      )}

      {!dashboard.isError && dashboard.data?.is_empty && (
        <EmptyState
          icon={chartIcon}
          title="За этот период заявок не было"
          description="Выберите период длиннее"
        />
      )}

      {dashboard.isSuccess && !dashboard.data.is_empty && (
        <Flex direction="column" align="stretch" gapY={20}>
          <TilesSection tiles={dashboard.data.tiles} />

          <ChartsSection charts={dashboard.data.charts} />
        </Flex>
      )}

      <MetersSection />

      <ChannelsSection period={period} />

      <ExecutorsSection period={period} />

      <BenchmarkLink />
    </Panel>
  );
};

export const Component = AdminAnalyticsPage;
