import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import {
  CATEGORY_ICON,
  type RequestStatus,
  STATUS_TONE,
} from "@/features/request";
import { formatShortDay, formatTime, plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Card } from "@/shared/ui/card";
import { Chevron } from "@/shared/ui/chevron";
import { checkIcon, usersIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { useHouseProblems } from "./use-house-problems";

import styles from "./house-problems.module.css";

const HouseProblemsPage = () => {
  const problems = useHouseProblems();

  if (problems.isPending) {
    return <LoadingState fill title="Загружаем проблемы дома" />;
  }

  if (problems.isError) {
    return (
      <ErrorState
        error={problems.error}
        fill
        onRetry={() => void problems.refetch()}
      />
    );
  }

  const { open, resolved, resolved_total: resolvedTotal } = problems.data;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text variant="detail" color="secondary">
        О чем соседи уже сообщили в УК. Имен, номеров квартир и текстов заявок
        здесь нет
      </Typography.Text>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Сейчас открыто: {open.length}</h2>
          </Typography.Text>

          {open.length === 0 && (
            <EmptyState
              icon={resolvedTotal > 0 ? checkIcon : usersIcon}
              title={
                resolvedTotal > 0
                  ? "Все проблемы, о которых сообщали соседи, решены"
                  : "О проблемах пока не сообщали"
              }
              description="Когда кто-то в доме подаст заявку, здесь появятся ее категория и статус"
            />
          )}

          {open.map((problem, index) => (
            <Card key={`${problem.category}-${index}`}>
              <Flex align="center" gap={12}>
                <IconTile
                  icon={CATEGORY_ICON[problem.category]}
                  tone={STATUS_TONE[problem.status]}
                />
                <Flex
                  className={styles.Grow}
                  align="stretch"
                  direction="column"
                  gapY={2}
                >
                  <Flex align="center" gap={8}>
                    <Typography.Text
                      variant="body-strong"
                      color="primary"
                      className={styles.Grow}
                    >
                      {problem.category_label}
                    </Typography.Text>
                    <StatusPill tone={STATUS_TONE[problem.status]}>
                      {
                        (
                          {
                            new: "Ждет УК",
                            accepted: "УК приняла",
                            in_progress: "В работе",
                            on_review: "Сделано, проверяют",
                            done: "Решена",
                          } satisfies Record<RequestStatus, string>
                        )[problem.status]
                      }
                    </StatusPill>
                  </Flex>
                  <Typography.Text variant="description" color="secondary">
                    {problem.flats_count}{" "}
                    {plural(problem.flats_count, [
                      "квартира сообщила",
                      "квартиры сообщили",
                      "квартир сообщили",
                    ])}{" "}
                    · с {formatTime(problem.since)}{" "}
                    {formatShortDay(problem.since)}
                  </Typography.Text>
                  {problem.mine && (
                    <Typography.Text
                      variant="description"
                      className={styles.Mine}
                    >
                      Вы тоже сообщили
                    </Typography.Text>
                  )}
                </Flex>
              </Flex>

              {!problem.mine && (
                <Button asChild size="medium" variant="secondary" stretched>
                  <Link
                    to={`${Routes.REQUEST_NEW}?category=${problem.category}`}
                  >
                    У меня тоже
                  </Link>
                </Button>
              )}
            </Card>
          ))}
        </section>
      </Flex>

      {resolvedTotal > 0 && (
        <details className={styles.Resolved}>
          <summary className={styles.Summary}>
            <Typography.Text
              variant="body-strong"
              color="primary"
              className={styles.Grow}
            >
              Решенные за 30 дней ({resolvedTotal})
            </Typography.Text>
            <span className={styles.Chevron}>
              <Chevron />
            </span>
          </summary>

          {resolved.map((problem, index) => (
            <Flex
              key={`${problem.category}-${index}`}
              className={styles.Row}
              align="center"
              gap={12}
            >
              <IconTile
                icon={CATEGORY_ICON[problem.category]}
                tone={problem.confirmed ? "positive" : "neutral"}
              />
              <Flex
                className={styles.Grow}
                align="stretch"
                direction="column"
                gapY={2}
              >
                <Typography.Text variant="body-strong" color="primary">
                  {problem.category_label}
                </Typography.Text>
                <Typography.Text variant="description" color="secondary">
                  решена {formatShortDay(problem.done_at)} ·{" "}
                  {problem.confirmed
                    ? "житель подтвердил"
                    : "закрыта автоматически"}
                </Typography.Text>
              </Flex>
            </Flex>
          ))}

          {resolvedTotal > resolved.length && (
            <Typography.Text
              asChild
              variant="description"
              color="tertiary"
              className={styles.Note}
            >
              <p>Показаны последние {resolved.length}</p>
            </Typography.Text>
          )}
        </details>
      )}
    </Panel>
  );
};

export const Component = HouseProblemsPage;
