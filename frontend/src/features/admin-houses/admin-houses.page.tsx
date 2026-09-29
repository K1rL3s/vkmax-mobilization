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
import { generatePath, Link, useNavigate } from "react-router-dom";

import { errorDetail, isForbidden } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { nextOffset } from "@/shared/api/next-offset";
import type { components } from "@/shared/api/schema/generated";
import { cn } from "@/shared/lib/css";
import { plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { orgParams, useSession } from "@/shared/model/session";
import { Chevron } from "@/shared/ui/chevron";
import { homeIcon, Icon, searchOutlineIcon, usersIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { useAdminMap } from "./model/use-admin-map";
import { HousesMap } from "./ui/houses-map";

import styles from "./admin-houses.module.css";

type House = components["schemas"]["AdminHouseListItem"];

const HouseRow = ({ house, isAdmin }: { house: House; isAdmin: boolean }) => {
  const navigate = useNavigate();

  const requests =
    house.open_requests > 0 ? (
      <StatusPill tone="themed">
        {house.open_requests}{" "}
        {plural(house.open_requests, ["заявка", "заявки", "заявок"])} в работе
      </StatusPill>
    ) : (
      <StatusPill tone="neutral">Заявок в работе нет</StatusPill>
    );

  if (!isAdmin) {
    return (
      <div className={styles.Row}>
        <IconTile icon={homeIcon} tone="neutral" />

        <Flex
          className={styles.Grow}
          align="stretch"
          direction="column"
          gapY={4}
        >
          <Typography.Text variant="body-strong" color="primary">
            {house.address}
          </Typography.Text>

          <Flex align="center" gap={6} wrap="wrap">
            {requests}
          </Flex>
        </Flex>
      </div>
    );
  }

  return (
    <Tappable
      className={styles.Row}
      onClick={() =>
        void navigate(
          generatePath(Routes.ADMIN_HOUSE, { houseId: String(house.id) }),
        )
      }
    >
      <IconTile icon={homeIcon} tone="neutral" />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
        <Typography.Text variant="body-strong" color="primary">
          {house.address}
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {house.flats_count}{" "}
          {plural(house.flats_count, ["квартира", "квартиры", "квартир"])}
          {house.residents_count != null &&
            ` · ${house.residents_count} ${plural(house.residents_count, ["житель", "жителя", "жителей"])}`}
        </Typography.Text>

        <Flex align="center" gap={6} wrap="wrap">
          {requests}

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

const HouseList = ({ isAdmin }: { isAdmin: boolean }) => {
  const navigate = useNavigate();
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
          icon={homeIcon}
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
          icon={homeIcon}
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
          icon={homeIcon}
          title="Домов пока нет"
          description="Дома попадают в организацию из открытого реестра: те, у которых ваша УК указана управляющей. Если дома нет в списке, проверьте, что в реестре у него указана ваша организация"
        />
      );
    }

    return (
      <>
        {items.map((house) => (
          <HouseRow key={house.id} house={house} isAdmin={isAdmin} />
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
    <>
      <div className={styles.Panel}>
        <CellSimple
          before={<Icon src={usersIcon} className={styles.CellIcon} />}
          title="Организация и сотрудники"
          subtitle={
            isAdmin
              ? "Реквизиты, настройки, приглашения сотрудников"
              : "Настройки организации для просмотра"
          }
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
          mode="contrast"
          onChange={(event) => setQuery(event.target.value)}
        />
      )}

      {content()}
    </>
  );
};

const AdminHousesPage = () => {
  const { currentOrg } = useSession();
  const map = useAdminMap();
  const view = map.filters.view;

  return (
    <Panel
      className={cn(styles.Page, view === "map" && styles.mapped)}
      mode="secondary"
    >
      <div className={styles.Header}>
        <Flex
          className={styles.Grow}
          align="stretch"
          direction="column"
          gapY={4}
        >
          <Typography.Text asChild variant="title" color="primary">
            <h1>Дома</h1>
          </Typography.Text>

          {currentOrg && (
            <Link
              to={Routes.ADMIN_ORG}
              className={styles.Org}
              aria-label={`${currentOrg.name}: организация и сотрудники`}
            >
              <Typography.Text variant="description" color="secondary">
                {currentOrg.name}
              </Typography.Text>
              <Chevron />
            </Link>
          )}
        </Flex>

        <div className={styles.Views} role="radiogroup" aria-label="Вид">
          {(
            [
              { id: "map", label: "Карта" },
              { id: "list", label: "Список" },
            ] as const
          ).map((option) => (
            <Button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={view === option.id}
              size="small"
              variant={view === option.id ? "primary" : "secondary"}
              onClick={() =>
                map.update({ view: option.id === "map" ? null : "list" })
              }
            >
              {option.label}
            </Button>
          ))}
        </div>
      </div>

      {view === "map" ? (
        <HousesMap map={map} />
      ) : (
        <HouseList isAdmin={map.isAdmin} />
      )}
    </Panel>
  );
};

export const Component = AdminHousesPage;
