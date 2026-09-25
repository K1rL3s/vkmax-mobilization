import { EmptyState } from "@/shared/ui/state";

import { formatMetric } from "../domain/metric";
import type { PeriodDays } from "../domain/period";
import { useExecutors } from "../model/use-executors";

import { Section } from "./section";
import styles from "./executors-section.module.css";

const dash = (value: number | null | undefined, unit: "minutes" | "points") =>
  value === null || value === undefined ? "—" : formatMetric(value, unit);

export const ExecutorsSection = ({ period }: { period: PeriodDays }) => {
  const executors = useExecutors(period);

  return (
    <Section
      title="Исполнители"
      isPending={executors.isPending}
      isError={executors.isError}
      onRetry={() => void executors.refetch()}
    >
      {executors.data?.length === 0 ? (
        <EmptyState
          title="В организации нет сотрудников с ролью «исполнитель»"
          description="Исполнителя приглашают диплинком в настройках организации"
        />
      ) : (
        <div className={styles.Scroll}>
          <table className={styles.Table}>
            <thead>
              <tr>
                <th className={styles.Name} scope="col">
                  Исполнитель
                </th>
                <th scope="col">Закрыто</th>
                <th scope="col">Медиана</th>
                <th scope="col">Оценка</th>
                <th scope="col">Повторные</th>
              </tr>
            </thead>

            <tbody>
              {executors.data?.map((executor) => (
                <tr key={executor.user_id}>
                  <th className={styles.Name} scope="row">
                    {executor.name}
                  </th>
                  <td>{executor.closed}</td>
                  <td>{dash(executor.median_time, "minutes")}</td>
                  <td>{dash(executor.rating, "points")}</td>
                  <td>{formatMetric(executor.repeat_share, "percent")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
};
