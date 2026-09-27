import { useState } from "react";
import {
  Button,
  CellSimple,
  Flex,
  Input,
  Panel,
  Tappable,
  Typography,
} from "@maxhub/max-ui";
import { useDebounceValue } from "@siberiacancode/reactuse";
import { keepPreviousData } from "@tanstack/react-query";
import { generatePath, useNavigate } from "react-router-dom";

import { errorDetail, isForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { nextOffset } from "@/shared/api/next-offset";
import type { components } from "@/shared/api/schema/generated";
import { plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { orgParams, useSession } from "@/shared/model/session";
import { Chevron } from "@/shared/ui/chevron";
import {
  buildingIcon,
  Icon,
  searchOutlineIcon,
  usersIcon,
} from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import styles from "./admin-houses.module.css";

type House = components["schemas"]["AdminHouseListItem"];

const HouseRow = ({ house }: { house: House }) => {
  const navigate = useNavigate();

  return (
    <Tappable
      className={styles.Row}
      onClick={() =>
        void navigate(
          generatePath(Routes.ADMIN_HOUSE, { houseId: String(house.id) }),
        )
      }
    >
      <IconTile icon={buildingIcon} tone="themed" />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
        <Typography.Text variant="body-strong" color="primary">
          {house.address}
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {house.flats_count}{" "}
          {plural(house.flats_count, ["квартира", "квартиры", "квартир"])} ·{" "}
          {house.residents_count}{" "}
          {plural(house.residents_count, ["житель", "жителя", "жителей"])}
        </Typography.Text>

        <Flex align="center" gap={6} wrap="wrap">
          {house.open_requests > 0 ? (
            <StatusPill tone="themed">
              {house.open_requests}{" "}
              {plural(house.open_requests, ["заявка", "заявки", "заявок"])} в
              работе
            </StatusPill>
          ) : (
            <StatusPill tone="neutral">Заявок в работе нет</StatusPill>
          )}

          {house.chat_bound ? (
            <StatusPill tone="positive">Чат привязан</StatusPill>
          ) : (
            <StatusPill tone="neutral">Без чата</StatusPill>
          )}
        </Flex>
      </Flex>

      <Chevron />
    </Tappable>
  );
};

const AdminHousesPage = () => {
  const navigate = useNavigate();
  const { currentOrg } = useSession();
  const [query, setQuery] = useState("");
  const search = useDebounceValue(query.trim(), 300);

  const houses = rqClient.useInfiniteQuery(
    "get",
    "/api/admin/houses",
    {
      params: {
        ...orgParams(),
        query: { q: search || undefined, limit: 50 },
      },
    },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: nextOffset,
      placeholderData: keepPreviousData,
    },
  );

  const items = houses.data?.pages.flatMap((page) => page.items) ?? [];

  const content = () => {
    if (houses.isPending) {
      return <LoadingState fill title="Загружаем дома" />;
    }

    if (isForbidden(houses.error)) {
      return (
        <EmptyState
          fill
          icon={buildingIcon}
          title="Дома видит администратор"
          description={
            errorDetail(houses.error) ??
            "Попросите создателя организации выдать вам права администратора"
          }
        />
      );
    }

    if (houses.isError) {
      return (
        <ErrorState
          error={houses.error}
          fill
          onRetry={() => void houses.refetch()}
        />
      );
    }

    if (items.length === 0 && search !== "") {
      return (
        <EmptyState
          fill
          icon={buildingIcon}
          title="Ничего не нашли"
          description="Ищите по названию улицы или номеру дома"
          action={
            <Button
              size="medium"
              variant="secondary"
              onClick={() => setQuery("")}
            >
              Сбросить поиск
            </Button>
          }
        />
      );
    }

    if (items.length === 0) {
      return (
        <EmptyState
          fill
          icon={buildingIcon}
          title="Домов пока нет"
          description="Дома попадают в организацию из открытого реестра: те, у которых ваша УК указана управляющей. Если дома нет в списке, проверьте, что в реестре у него указана ваша организация"
        />
      );
    }

    return (
      <>
        {items.map((house) => (
          <HouseRow key={house.id} house={house} />
        ))}

        {houses.hasNextPage && (
          <Button
            size="medium"
            variant="secondary"
            loading={houses.isFetchingNextPage}
            onClick={() => void houses.fetchNextPage()}
          >
            Показать ещё
          </Button>
        )}
      </>
    );
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>Дома</h1>
        </Typography.Text>

        {currentOrg && (
          <Typography.Text variant="description" color="secondary">
            {currentOrg.name}
          </Typography.Text>
        )}
      </Flex>

      <div className={styles.Panel}>
        <CellSimple
          before={<Icon src={usersIcon} className={styles.CellIcon} />}
          title="Организация и сотрудники"
          subtitle="Реквизиты, настройки, приглашения сотрудников"
          showChevron
          onClick={() => void navigate(Routes.ADMIN_ORG)}
        />
      </div>

      {(query !== "" || items.length > 0) && (
        <Input
          placeholder="Улица или номер дома"
          maxLength={100}
          iconBefore={<Icon src={searchOutlineIcon} size={20} />}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      )}

      {content()}
    </Panel>
  );
};

export const Component = AdminHousesPage;
