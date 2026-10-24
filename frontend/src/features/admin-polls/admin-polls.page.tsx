import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import { orgParams } from "@/shared/model/session";
import { Disclosure } from "@/shared/ui/disclosure";
import { pollIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { AdminPollRow } from "./admin-poll-row";

import styles from "./admin-polls.module.css";

const AdminPollsPage = () => {
  const polls = rqClient.useQuery("get", "/api/admin/polls", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

  const items = polls.data?.items ?? [];
  const total = polls.data?.total ?? 0;
  const active = items.filter((poll) => poll.status === "active");
  const closed = items.filter((poll) => poll.status === "closed");

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text asChild variant="header" color="primary">
        <h1>Опросы</h1>
      </Typography.Text>

      {polls.isPending && <LoadingState fill title="Загружаем опросы" />}

      {polls.isError && (
        <ErrorState
          error={polls.error}
          fill
          onRetry={() => void polls.refetch()}
        />
      )}

      {polls.isSuccess && items.length === 0 && (
        <EmptyState
          fill
          icon={pollIcon}
          title="Опросов пока нет"
          description="Опрос дома заводит управляющая компания здесь или председатель совета дома в своём кабинете. Жители голосуют в мини-приложении, а итоги с кворумом по площади появятся в этом списке."
          action={
            <Button asChild size="medium">
              <Link to={Routes.ADMIN_POLL_NEW}>Новый опрос</Link>
            </Button>
          }
        />
      )}

      {items.length > 0 && (
        <Button asChild size="large" stretched>
          <Link to={Routes.ADMIN_POLL_NEW}>Новый опрос</Link>
        </Button>
      )}

      {active.length > 0 && (
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Идут</h2>
            </Typography.Text>

            {active.map((poll) => (
              <AdminPollRow key={poll.id} poll={poll} />
            ))}
          </section>
        </Flex>
      )}

      {closed.length > 0 && (
        <Disclosure title={`Завершённые (${closed.length})`}>
          <Flex align="stretch" direction="column" gap={8}>
            {closed.map((poll) => (
              <AdminPollRow key={poll.id} poll={poll} />
            ))}
          </Flex>
        </Disclosure>
      )}

      {total > items.length && (
        <Typography.Text variant="description" color="secondary">
          Показаны первые {items.length} из {total} опросов
        </Typography.Text>
      )}

      <Typography.Text variant="description" color="secondary">
        Предварительный сбор позиций собственников. Это не общее собрание
        собственников (ОСС) по ЖК РФ
      </Typography.Text>
    </Panel>
  );
};

export const Component = AdminPollsPage;
