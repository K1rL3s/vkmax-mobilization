import { Flex, Panel, Typography } from "@maxhub/max-ui";

import { formatTime } from "@/shared/lib/format";
import { homeIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import {
  accessWindows,
  placesLeftLabel,
  respondedLabel,
  unansweredFlats,
  type AccessTarget,
} from "./domain/access";
import { dayTitle } from "./domain/day";
import { useAccessRequest, useWithoutCell } from "./model/use-access";

import styles from "./admin-access.module.css";

const Flats = ({ numbers }: { numbers: string[] }) => (
  <div className={styles.Flats}>
    {numbers.map((number) => (
      <Typography.Text
        key={number}
        className={styles.Flat}
        variant="body"
        color="primary"
      >
        кв. {number}
      </Typography.Text>
    ))}
  </div>
);

const numbersOf = (flats: AccessTarget[]) =>
  flats.map((flat) => flat.flat_number);

const AdminAccessPage = () => {
  const { valid, query: grid } = useAccessRequest();
  const withoutCell = useWithoutCell();

  if (!valid || grid.isError) {
    return (
      <ErrorState
        error={grid.error}
        fill
        description="Не получилось загрузить сбор доступа"
        onRetry={() => void grid.refetch()}
      />
    );
  }

  if (grid.isPending) {
    return <LoadingState fill title="Загружаем сбор доступа" />;
  }

  const item = grid.data.access_request;
  const windows = accessWindows(grid.data);
  const waiting = unansweredFlats(grid.data);

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex align="flex-start" gap={12}>
          <IconTile icon={homeIcon} tone="promo" />

          <Flex
            align="stretch"
            direction="column"
            gapY={2}
            className={styles.Grow}
          >
            <Typography.Text asChild variant="title" color="primary">
              <h1 className={styles.Title}>{item.reason}</h1>
            </Typography.Text>

            <Typography.Text variant="description" color="secondary">
              {item.address}
            </Typography.Text>
          </Flex>
        </Flex>

        <Typography.Text variant="body" color="primary">
          {dayTitle(item.date)} · {respondedLabel(item)}
        </Typography.Text>

        {windows.length === 0 ? (
          <EmptyState
            title="У сбора нет окон"
            description="Жителям нечего выбирать: заведите сбор заново с окнами доступа"
          />
        ) : (
          windows.map((window) => (
            <section key={window.slot.id} className={styles.Window}>
              <Flex align="center" gap={8}>
                <Typography.Text
                  asChild
                  className={styles.Grow}
                  variant="body-strong"
                  color="primary"
                >
                  <h2 className={styles.Title}>
                    с {formatTime(window.slot.starts_at)}
                  </h2>
                </Typography.Text>

                <StatusPill
                  tone={
                    window.flats.length < window.slot.capacity
                      ? "themed"
                      : "neutral"
                  }
                >
                  {placesLeftLabel(window)}
                </StatusPill>
              </Flex>

              {window.flats.length === 0 ? (
                <Typography.Text variant="description" color="secondary">
                  Это окно пока никто не выбрал
                </Typography.Text>
              ) : (
                <Flats numbers={numbersOf(window.flats)} />
              )}
            </section>
          ))
        )}

        {withoutCell.length > 0 && (
          <section className={styles.Window}>
            <Typography.Text asChild variant="body-strong" color="primary">
              <h2 className={styles.Title}>Этим квартирам не досталось окна</h2>
            </Typography.Text>

            <Typography.Text variant="description" color="secondary">
              Открыть в них некому: подтверждённого жителя нет или он
              заблокирован. В сборе этих квартир нет - договоритесь с ними
              отдельно
            </Typography.Text>

            <Flats numbers={withoutCell} />
          </section>
        )}

        {waiting.length > 0 && (
          <section className={styles.Window}>
            <Typography.Text asChild variant="body-strong" color="primary">
              <h2 className={styles.Title}>Не ответили</h2>
            </Typography.Text>

            <Typography.Text variant="description" color="secondary">
              Эти квартиры окно ещё не выбрали. Напоминание из кабинета не
              уходит - договариваться с ними придётся самим
            </Typography.Text>

            <Flats numbers={numbersOf(waiting)} />
          </section>
        )}
      </div>
    </Panel>
  );
};

export const Component = AdminAccessPage;
