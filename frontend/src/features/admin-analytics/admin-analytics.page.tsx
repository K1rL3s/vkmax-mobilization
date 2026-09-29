import { Flex, Panel, Typography } from "@maxhub/max-ui";
import { useSearchParams } from "react-router-dom";

import { FilterBar } from "@/features/admin-requests";
import { chartIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { PERIODS } from "./domain/period";
import { useDashboard } from "./model/use-dashboard";
import { BenchmarkLink } from "./ui/benchmark-link";
import { ChannelsSection } from "./ui/channels-section";
import { ChartsSection } from "./ui/charts-section";
import { ExecutorsSection } from "./ui/executors-section";
import { MetersSection } from "./ui/meters-section";
import { TilesSection } from "./ui/tiles-section";

import styles from "./admin-analytics.module.css";

const AdminAnalyticsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const selected =
    PERIODS.find(({ days }) => String(days) === searchParams.get("period")) ??
    PERIODS[1];
  const period = selected.days;
  const dashboard = useDashboard(period);

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
        <Typography.Text asChild variant="header" color="primary">
          <h1>Аналитика</h1>
        </Typography.Text>

        <FilterBar
          groups={[
            {
              name: "period",
              label: "Период",
              options: PERIODS.map(({ days, label }) => ({
                id: String(days),
                label,
              })),
              value: String(period),
              defaultValue: "30",
            },
          ]}
          onChange={(_, days) =>
            setSearchParams(days === "30" ? {} : { period: days }, {
              replace: true,
            })
          }
        />
      </Flex>

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
          <TilesSection
            tiles={dashboard.data.tiles}
            periodTitle={selected.title}
          />

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
