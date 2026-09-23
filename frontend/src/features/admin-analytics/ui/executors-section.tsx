import type { components } from "@/shared/api/schema/generated";
import { EmptyState } from "@/shared/ui/state";

import { formatMetric } from "../domain/metric";

import { Section } from "./section";
import styles from "./executors-section.module.css";

type ExecutorsSectionProps = {
  isPending: boolean;
  isError: boolean;
  isEmpty: boolean;
  onRetry: () => void;
  items: components["schemas"]["ExecutorStatsItem"][];
};

// ноль в медиане и оценке значит «закрытых заявок не было», а не «ноль минут»
// и «оценка ноль», поэтому пустое приезжает как null и рисуется прочерком
const dash = (value: number | null | undefined, unit: "minutes" | "points") =>
  value === null || value === undefined ? "—" : formatMetric(value, unit);

export const ExecutorsSection = ({
  isPending,
  isError,
  isEmpty,
  onRetry,
  items,
}: ExecutorsSectionProps) => (
  <Section
    title="Исполнители"
    isPending={isPending}
    isError={isError}
    onRetry={onRetry}
  >
    {isEmpty ? (
      <EmptyState
        title="В организации нет сотрудников с ролью «исполнитель»"
        description="Исполнителя приглашают диплинком в настройках организации"
      />
    ) : (
      /* имя закреплено слева, числа уезжают вбок внутри этого контейнера:
         страница вбок не едет */
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
            {items.map((executor) => (
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
