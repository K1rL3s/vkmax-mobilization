import { Typography } from "@maxhub/max-ui";

import { EmptyState } from "@/shared/ui/state";

import { formatMetric } from "../domain/metric";
import type { PeriodDays } from "../domain/period";
import { useExecutors } from "../model/use-executors";

import { Section } from "./section";
import styles from "./executors-section.module.css";

const dash = (value: number | null | undefined, unit: "minutes" | "points") =>
  value === null || value === undefined ? "-" : formatMetric(value, unit);

export const ExecutorsSection = ({ period }: { period: PeriodDays }) => {
  const executors = useExecutors(period);

  return (
    <Section
      title="Исполнители"
      isPending={executors.isPending}
      isError={executors.isError}
      error={executors.error}
      onRetry={() => void executors.refetch()}
    >
      {executors.data?.length === 0 ? (
        <EmptyState
          title="В организации нет сотрудников с ролью «исполнитель»"
          description="Исполнителя приглашают диплинком в настройках организации"
        />
      ) : (
        <div>
          {executors.data?.map((executor) => (
            <div key={executor.user_id} className={styles.Row}>
              <Typography.Text variant="body-strong" color="primary">
                {executor.name}
              </Typography.Text>

              <div className={styles.Metrics}>
                {[
                  ["закрыто", String(executor.closed)],
                  ["медиана", dash(executor.median_time, "minutes")],
                  ["оценка", dash(executor.rating, "points")],
                  ["повторные", formatMetric(executor.repeat_share, "percent")],
                ].map(([label, value]) => (
                  <Typography.Text
                    key={label}
                    variant="detail"
                    color="secondary"
                  >
                    {label} <span className={styles.Value}>{value}</span>
                  </Typography.Text>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
};
