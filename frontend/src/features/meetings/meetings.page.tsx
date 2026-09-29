import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { pollIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { usePollList } from "./model/use-poll-list";
import { PollRow } from "./ui/poll-row";

import styles from "./meetings.module.css";

const MeetingsPage = () => {
  const list = usePollList();

  return (
    <Panel className={styles.Page} mode="secondary">
      {list.isChairman && list.isConnected && (
        <Button asChild size="large" stretched>
          <Link to={Routes.MEETING_NEW}>Создать опрос</Link>
        </Button>
      )}

      {list.canPropose && (
        <Button
          asChild
          size="large"
          stretched
          variant={list.isChairman ? "secondary" : "primary"}
        >
          <Link to={Routes.MEETING_INITIATIVE_NEW}>Предложить инициативу</Link>
        </Button>
      )}

      {!list.isConnected && (
        <EmptyState
          fill
          icon={pollIcon}
          title="Опросы появятся вместе с УК"
          description="Дом ещё не подключён к сервису. Опросы дома заводит управляющая компания или председатель совета дома."
        />
      )}

      {list.isConnected && list.isPending && (
        <LoadingState fill title="Загружаем опросы" />
      )}

      {list.isConnected && list.isError && (
        <ErrorState error={list.loadError} fill onRetry={list.retry} />
      )}

      {list.isConnected && !list.isPending && !list.isError && list.isEmpty && (
        <EmptyState
          fill
          icon={pollIcon}
          title="Опросов пока нет"
          description="Здесь появятся опросы дома. Их заводит председатель совета дома или управляющая компания."
        />
      )}

      {list.sections.map((section) => (
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
              <PollRow key={poll.id} poll={poll} />
            ))}
          </section>
        </Flex>
      ))}
    </Panel>
  );
};

export const Component = MeetingsPage;
