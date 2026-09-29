import { CellSimple, Counter, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";
import { z } from "zod";

import {
  errorDetail,
  isForbidden,
  retryUnlessForbidden,
} from "@/shared/api/errors";
import { HouseSummary } from "@/features/house";
import { rqClient } from "@/shared/api/instance";
import type { components } from "@/shared/api/schema/generated";
import { formatArea, plural } from "@/shared/lib/format";
import { useRouteParams } from "@/shared/lib/router";
import { Routes } from "@/shared/model/routes";
import { orgParams } from "@/shared/model/session";
import { clockIcon, homeIcon, Icon, qrIcon, usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { ChatSection } from "./ui/chat-section";
import { ReadingsSection } from "./ui/readings-section";
import { ResidentsSection } from "./ui/residents-section";

import styles from "./admin-house.module.css";

type HouseCard = components["schemas"]["AdminHouseCard"];

const Facts = ({ house }: { house: HouseCard }) => {
  const facts: { label: string; value: string; wide?: boolean }[] = [
    { label: "Подъездов", value: String(house.entrances) },
  ];

  if (house.floors != null) {
    facts.push({ label: "Этажей", value: String(house.floors) });
  }

  if (house.built_year != null) {
    facts.push({ label: "Год постройки", value: String(house.built_year) });
  }

  if (house.area != null) {
    facts.push({ label: "Площадь дома", value: formatArea(house.area) });
  }

  facts.push(
    {
      label: "Кадастровый номер",
      value: house.cadastral_no ?? "Не указан",
      wide: true,
    },
    {
      label: "Председатель совета дома",
      value: house.chairman_name ?? "Не назначен, назначьте из списка жителей",
      wide: true,
    },
  );

  return (
    <div className={styles.Facts}>
      {facts.map((fact) => (
        <Flex
          key={fact.label}
          direction="column"
          gapY={2}
          className={fact.wide ? styles.wide : undefined}
        >
          <Typography.Text variant="description" color="secondary">
            {fact.label}
          </Typography.Text>
          <Typography.Text variant="body-strong" color="primary">
            {fact.value}
          </Typography.Text>
        </Flex>
      ))}
    </div>
  );
};

const Stat = ({ value, label }: { value: number; label: string }) => (
  <Flex className={styles.Stat} direction="column" gapY={2}>
    <Typography.Text variant="header" color="primary">
      {value}
    </Typography.Text>
    <Typography.Text variant="description" color="secondary">
      {label}
    </Typography.Text>
  </Flex>
);

const AdminHousePage = () => {
  const navigate = useNavigate();
  const params = useRouteParams(
    z.object({ houseId: z.coerce.number().int().positive() }),
  );
  const houseId = params?.houseId ?? 0;

  const card = rqClient.useQuery(
    "get",
    "/api/admin/houses/{house_id}",
    { params: { ...orgParams(), path: { house_id: houseId } } },
    {
      enabled: params !== null,
      retry: (failures, error) =>
        error.status !== 404 && retryUnlessForbidden(failures, error),
    },
  );

  if (params === null || card.error?.status === 404) {
    return (
      <EmptyState
        fill
        icon={homeIcon}
        title="Дом не найден"
        description="Такого дома нет среди домов вашей организации. Откройте дом из списка на вкладке «Дома»"
      />
    );
  }

  if (card.isPending) {
    return <LoadingState fill title="Загружаем карточку дома" />;
  }

  if (isForbidden(card.error)) {
    return (
      <EmptyState
        fill
        icon={homeIcon}
        title="Нет доступа к дому"
        description={errorDetail(card.error) ?? "Нужны права администратора"}
      />
    );
  }

  if (card.isLoadingError) {
    return (
      <ErrorState error={card.error} fill onRetry={() => void card.refetch()} />
    );
  }

  const house = card.data;
  const pending = house.pending_verifications;

  return (
    <Panel className={styles.Page} mode="secondary">
      <HouseSummary
        as="h1"
        title={house.address}
        state="plain"
        subtitle={house.region}
      />

      <div className={styles.Stats}>
        <Stat
          value={house.flats_count}
          label={plural(house.flats_count, ["квартира", "квартиры", "квартир"])}
        />
        <Stat
          value={house.residents_count}
          label={plural(house.residents_count, ["житель", "жителя", "жителей"])}
        />
        <Stat
          value={house.verified_residents_count}
          label="с подтверждённой квартирой"
        />
        <Stat
          value={house.open_requests}
          label={`${plural(house.open_requests, ["заявка", "заявки", "заявок"])} в работе`}
        />
      </div>

      <Facts house={house} />

      <div className={styles.Panel}>
        <CellSimple
          before={<Icon src={usersIcon} className={styles.CellIcon} />}
          title="Запросы подтверждения"
          subtitle={
            pending > 0
              ? "Жители, у которых не совпал лицевой счёт"
              : "Очередь по этому дому пуста"
          }
          after={pending > 0 && <Counter value={pending} rounded />}
          showChevron
          onClick={() =>
            void navigate({
              pathname: Routes.ADMIN_VERIFICATIONS,
              search: `?house_id=${house.id}`,
            })
          }
        />
        <CellSimple
          separator
          before={<Icon src={qrIcon} className={styles.CellIcon} />}
          title="QR-коды дома"
          subtitle={
            house.entrances > 0
              ? `${house.entrances} ${plural(house.entrances, ["подъезд", "подъезда", "подъездов"])}, печать на A4`
              : "У дома не указаны подъезды, печатать нечего"
          }
          disabled={house.entrances === 0}
          showChevron
          onClick={() =>
            void navigate(
              generatePath(Routes.ADMIN_HOUSE_QR, {
                houseId: String(house.id),
              }),
            )
          }
        />
        <CellSimple
          separator
          before={<Icon src={clockIcon} className={styles.CellIcon} />}
          title="Окно подачи показаний"
          subtitle="Задаётся для всей организации в её настройках"
          showChevron
          onClick={() =>
            void navigate({ pathname: Routes.ADMIN_ORG, hash: "meter-window" })
          }
        />
      </div>

      <ChatSection house={house} />

      <ResidentsSection
        houseId={house.id}
        chairmanName={house.chairman_name ?? null}
      />

      <ReadingsSection houseId={house.id} />
    </Panel>
  );
};

export const Component = AdminHousePage;
