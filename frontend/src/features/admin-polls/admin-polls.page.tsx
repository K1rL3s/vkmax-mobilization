import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import { orgParams } from "@/shared/model/session";
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
  const sections = [
    {
      title: "Идут",
      items: items.filter((poll) => poll.status === "active"),
    },
    {
      title: "Завершены",
      items: items.filter((poll) => poll.status === "closed"),
    },
  ].filter((section) => section.items.length > 0);

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>Опросы</h1>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          Предварительный сбор позиций собственников. Это не общее собрание
          собственников (ОСС) по ЖК РФ
        </Typography.Text>
      </Flex>

      {polls.isPending && <LoadingState fill title="Загружаем опросы" />}

      {polls.isError && (
        <ErrorState fill onRetry={() => void polls.refetch()} />
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

      {sections.map((section) => (
        <Flex
          key={section.title}
          asChild
          align="stretch"
          direction="column"
          gap={8}
        >
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>{section.title}</h2>
            </Typography.Text>

            {section.items.map((poll) => (
              <AdminPollRow key={poll.id} poll={poll} />
            ))}
          </section>
        </Flex>
      ))}

      {total > items.length && (
        <Typography.Text variant="description" color="secondary">
          Показаны первые {items.length} из {total} опросов
        </Typography.Text>
      )}
    </Panel>
  );
};

export const Component = AdminPollsPage;
