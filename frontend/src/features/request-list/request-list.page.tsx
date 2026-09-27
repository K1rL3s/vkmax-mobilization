import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { DemandCard } from "@/features/home";
import { useHouseCard } from "@/features/house";
import { useSession } from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";
import { wrenchIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { RequestRow } from "./request-row";
import { StatusFilter } from "./status-filter";
import { useRequestList } from "./use-request-list";

import styles from "./request-list.module.css";

const RequestListPage = () => {
  const list = useRequestList();
  const { currentResidency: residency } = useSession();
  const card = useHouseCard(residency?.house_id);
  const house = card.data;
  const connected = house?.is_connected !== false;

  return (
    <Panel className={styles.Page} mode="secondary">
      {house && !connected ? (
        <DemandCard
          houseId={house.id}
          demandSent={house.demand_sent}
          demandCount={house.demand_count}
          onSent={() => void card.refetch()}
        />
      ) : (
        <Button asChild size="large" stretched>
          <Link to={Routes.REQUEST_NEW}>Новая заявка</Link>
        </Button>
      )}

      <StatusFilter value={list.filter} onChange={list.setFilter} />

      {list.isPending && <LoadingState fill title="Загружаем заявки" />}

      {list.isError && (
        <ErrorState error={list.loadError} fill onRetry={list.retry} />
      )}

      {list.isEmpty && connected && (
        <EmptyState
          fill
          icon={wrenchIcon}
          title="Заявок пока нет"
          description="Расскажите управляющей компании о проблеме: заявка попадёт диспетчеру, а срок ответа задаст категория."
        />
      )}

      {list.isFilterEmpty && (
        <EmptyState
          fill
          icon={wrenchIcon}
          title="В этом фильтре пусто"
          description="По выбранному статусу заявок нет."
          action={
            <Button
              size="medium"
              variant="secondary"
              onClick={() => list.setFilter("all")}
            >
              Показать все
            </Button>
          }
        />
      )}

      {list.groups.map((group) => (
        <Flex
          key={group.title}
          asChild
          align="stretch"
          direction="column"
          gap={8}
        >
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>{group.title}</h2>
            </Typography.Text>

            {group.items.map((request) => (
              <RequestRow key={request.id} request={request} />
            ))}
          </section>
        </Flex>
      ))}
    </Panel>
  );
};

export const Component = RequestListPage;
