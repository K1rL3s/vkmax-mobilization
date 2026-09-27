import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";

import { usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { useVerificationList } from "./model/use-verification-list";
import { StatusFilter } from "./ui/status-filter";
import { VerificationRow } from "./ui/verification-row";

import styles from "./admin-verifications.module.css";

const AdminVerificationsPage = () => {
  const list = useVerificationList();

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>Запросы подтверждения</h1>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {list.houseId === null
            ? "Все дома организации"
            : (list.houseAddress ?? "Выбранный дом")}
        </Typography.Text>
      </Flex>

      <StatusFilter value={list.status} onChange={list.setStatus} />

      {list.isPending && <LoadingState fill title="Загружаем запросы" />}

      {list.isError && (
        <ErrorState error={list.loadError} fill onRetry={list.retry} />
      )}

      {!list.isPending && !list.isError && list.isEmpty && (
        <EmptyState
          fill
          icon={usersIcon}
          title="Запросов нет"
          description="Сюда попадают жители, у которых не совпал лицевой счёт при автоматической сверке. Пустая очередь значит, что сверка прошла у всех."
        />
      )}

      {list.isHouseEmpty && (
        <EmptyState
          fill
          icon={usersIcon}
          title="По этому дому запросов нет"
          description={
            list.houseAddress
              ? `Жители дома ${list.houseAddress} подтвердили квартиры автоматической сверкой.`
              : "Жители этого дома подтвердили квартиры автоматической сверкой."
          }
        />
      )}

      {list.isFilterEmpty && (
        <EmptyState
          fill
          icon={usersIcon}
          title="В этом фильтре пусто"
          description="Здесь пусто, посмотрите в другом фильтре."
          action={
            <Button
              size="medium"
              variant="secondary"
              onClick={() => list.setStatus("all")}
            >
              Показать все
            </Button>
          }
        />
      )}

      {list.items.map((request) => (
        <VerificationRow
          key={request.id}
          request={request}
          showAddress={list.houseId === null}
        />
      ))}

      {list.isTruncated && (
        <Typography.Text variant="description" color="secondary">
          Показаны первые {list.loaded} из {list.total}, откройте очередь по
          конкретному дому
        </Typography.Text>
      )}
    </Panel>
  );
};

export const Component = AdminVerificationsPage;
