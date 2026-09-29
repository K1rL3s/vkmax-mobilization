import { Flex, Panel, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { chartIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { formatMetric } from "./domain/metric";
import { useBenchmark } from "./model/use-benchmark";
import { BenchmarkMetricRow } from "./ui/benchmark-metric";
import { Section } from "./ui/section";

import styles from "./admin-benchmark.module.css";

type BenchmarkRegionRow = components["schemas"]["BenchmarkRegionRow"];

const SplitRows = ({
  title,
  rows,
  pick,
}: {
  title: string;
  rows: BenchmarkRegionRow[];
  pick: (row: BenchmarkRegionRow) => string;
}) => {
  if (rows.length === 0) {
    return null;
  }

  return (
    <Flex direction="column" align="stretch" gapY={8}>
      <Typography.Text variant="detail-strong" color="secondary">
        {title}
      </Typography.Text>

      {rows.map((row) => (
        <Flex key={pick(row)} align="baseline" justify="space-between" gap={12}>
          <Typography.Text variant="detail" color="primary">
            {pick(row)}
          </Typography.Text>

          <Typography.Text
            className={styles.Value}
            variant="detail"
            color="secondary"
          >
            {formatMetric(row.value, row.unit)} · из {row.orgs_count} УК
          </Typography.Text>
        </Flex>
      ))}
    </Flex>
  );
};

const AdminBenchmarkPage = () => {
  const benchmark = useBenchmark();

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex direction="column" align="stretch" gapY={4}>
        <Typography.Text asChild variant="header" color="primary">
          <h1>Сравнение с другими УК</h1>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          За последние 30 дней
        </Typography.Text>
      </Flex>

      {benchmark.isPending && <LoadingState fill title="Считаем сравнение" />}

      {benchmark.isError && (
        <ErrorState
          error={benchmark.error}
          fill
          onRetry={() => void benchmark.refetch()}
        />
      )}

      {!benchmark.isError && benchmark.data?.is_empty && (
        <EmptyState
          fill
          icon={chartIcon}
          title="Сравнивать пока не с чем"
          description="Сравнение появится, когда в вашем регионе наберётся больше организаций с данными"
        />
      )}

      {benchmark.isSuccess && !benchmark.data.is_empty && (
        <>
          <Section title="Ваши показатели">
            <Flex direction="column" align="stretch" gapY={12}>
              {benchmark.data.metrics.map((metric) => (
                <BenchmarkMetricRow key={metric.key} metric={metric} />
              ))}
            </Flex>
          </Section>

          {benchmark.data.regions.length > 0 && (
            <Section
              title="Разрезы"
              note="Среднее время до принятия, медиана по УК разреза"
            >
              <Flex direction="column" align="stretch" gapY={12}>
                <SplitRows
                  title="По регионам"
                  rows={benchmark.data.regions.filter(
                    (row) => row.city == null,
                  )}
                  pick={(row) => row.region}
                />

                <SplitRows
                  title="По городам"
                  rows={benchmark.data.regions.filter(
                    (row) => row.city != null,
                  )}
                  pick={(row) => row.city ?? row.region}
                />
              </Flex>
            </Section>
          )}
        </>
      )}
    </Panel>
  );
};

export const Component = AdminBenchmarkPage;
