import { useState } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { Icon, plusIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import {
  respondedLabel,
  splitAccessRequests,
  type AccessRequest,
} from "../domain/access";
import { dayTitle } from "../domain/day";
import { useOrgAccessRequests } from "../model/use-access";
import { useIsOrgAdmin } from "../model/use-reception";

import styles from "./access-section.module.css";

const Row = ({ item }: { item: AccessRequest }) => (
  <Link
    className={styles.Row}
    to={Routes.ADMIN_ACCESS.replace(":accessRequestId", String(item.id))}
  >
    <Flex align="stretch" direction="column" gapY={2} className={styles.Grow}>
      <Typography.Text variant="body" color="primary">
        {item.address}
      </Typography.Text>

      <Typography.Text variant="description" color="secondary">
        {dayTitle(item.date)} · {respondedLabel(item)}
      </Typography.Text>

      <Typography.Text
        className={styles.Reason}
        variant="detail"
        color="tertiary"
      >
        {item.reason}
      </Typography.Text>
    </Flex>

    <Chevron />
  </Link>
);

const List = ({ items }: { items: AccessRequest[] }) => (
  <div className={styles.List}>
    {items.map((item) => (
      <Row key={item.id} item={item} />
    ))}
  </div>
);

// сбор доступа заводит администратор организации: список квартир требует тех
// же прав, что и часы приёма, поэтому кнопка у сотрудника без прав не ведёт
// в форму, из которой некого выбрать
const CreateAction = ({ canCreate }: { canCreate: boolean }) =>
  canCreate ? (
    <Button asChild size="medium" iconBefore={<Icon src={plusIcon} />}>
      <Link to={Routes.ADMIN_ACCESS_NEW}>Собрать доступ</Link>
    </Button>
  ) : (
    <Typography.Text variant="description" color="secondary">
      Собрать доступ может администратор организации
    </Typography.Text>
  );

export const AccessSection = () => {
  const canCreate = useIsOrgAdmin();
  const requests = useOrgAccessRequests();
  const [isPastOpen, setPastOpen] = useState(false);
  const { active, past } = splitAccessRequests(requests.data ?? []);

  return (
    <section className={styles.Section}>
      <Typography.Text asChild variant="title" color="primary">
        <h2>Сбор доступа</h2>
      </Typography.Text>

      {requests.isPending ? (
        <LoadingState title="Загружаем сборы доступа" />
      ) : requests.isError ? (
        <ErrorState
          description="Не получилось загрузить сборы доступа"
          onRetry={() => void requests.refetch()}
        />
      ) : requests.data.length === 0 ? (
        <EmptyState
          title="Сборов доступа ещё не было"
          description="Соберите доступ, когда нужно попасть сразу в несколько квартир: жители сами выберут удобное время"
          action={<CreateAction canCreate={canCreate} />}
        />
      ) : (
        <>
          <CreateAction canCreate={canCreate} />

          {active.length > 0 ? (
            <>
              <Typography.Text variant="detail" color="secondary">
                Идут
              </Typography.Text>
              <List items={active} />
            </>
          ) : (
            <Typography.Text variant="description" color="secondary">
              Идущих сборов нет — все прошли
            </Typography.Text>
          )}

          {past.length > 0 && (
            <>
              <button
                type="button"
                className={styles.Toggle}
                aria-expanded={isPastOpen}
                onClick={() => setPastOpen((open) => !open)}
              >
                <Typography.Text variant="detail" color="secondary">
                  Прошли · {past.length}
                </Typography.Text>

                <Typography.Text variant="detail" color="secondary">
                  {isPastOpen ? "Свернуть" : "Показать"}
                </Typography.Text>
              </button>

              {isPastOpen && <List items={past} />}
            </>
          )}
        </>
      )}
    </section>
  );
};
