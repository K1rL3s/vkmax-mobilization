import type { ReactNode } from "react";
import { Button, Flex, IconButton, Spinner, Typography } from "@maxhub/max-ui";

import type { HouseCard } from "@/features/house";
import { errorMessage } from "@/shared/api/errors";
import { formatPercent } from "@/shared/lib/format";
import { closeIcon, Icon } from "@/shared/ui/icon";
import { StatusPill } from "@/shared/ui/status-pill";

import type { PickedPlace } from "../model/use-point-pick";

import styles from "./house-sheet.module.css";

type HouseSheetProps = {
  place: PickedPlace;
  canPick: boolean;
  isAdding: boolean;
  addError: unknown;
  onChoose: (house: HouseCard) => void;
  onAdd: () => void;
  onClose: () => void;
};

const passport = (house: HouseCard) =>
  [
    house.built_year != null && `${house.built_year} г.`,
    house.floors != null && `${house.floors} эт.`,
  ]
    .filter(Boolean)
    .join(" · ");

const statsLine = (stats: NonNullable<HouseCard["org_stats"]>) =>
  [
    `В срок ${formatPercent(stats.on_time_share)}`,
    stats.rating != null &&
      `оценка ${(stats.rating / 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}`,
  ]
    .filter(Boolean)
    .join(" · ");

const Secondary = ({ children }: { children: ReactNode }) => (
  <Typography.Text variant="description" color="secondary">
    {children}
  </Typography.Text>
);

const Title = ({ children }: { children: ReactNode }) => (
  <Typography.Text asChild variant="title" color="primary">
    <h2 className={styles.Title}>{children}</h2>
  </Typography.Text>
);

const HouseDetails = ({
  house,
  canPick,
  onChoose,
}: {
  house: HouseCard;
  canPick: boolean;
  onChoose: (house: HouseCard) => void;
}) => (
  <>
    <Flex direction="column" align="stretch" gapY={4}>
      <Title>{house.address}</Title>
      {passport(house) && <Secondary>{passport(house)}</Secondary>}
    </Flex>

    {house.org && (
      <Flex direction="column" align="stretch" gapY={4}>
        <Flex align="center" gap={8} wrap="wrap">
          <Typography.Text variant="body-strong" color="primary">
            {house.org.name}
          </Typography.Text>
          {house.org.is_demo && <StatusPill tone="neutral">демо</StatusPill>}
        </Flex>
        {house.org_stats && <Secondary>{statsLine(house.org_stats)}</Secondary>}
      </Flex>
    )}

    {!house.is_connected && (
      <Flex direction="column" align="stretch" gapY={4}>
        <Typography.Text variant="body-strong" color="primary">
          УК не подключена
        </Typography.Text>
        {house.demand_count > 0 && (
          <Secondary>Ждут подключения: {house.demand_count}</Secondary>
        )}
      </Flex>
    )}

    {canPick && (
      <Button size="large" stretched onClick={() => onChoose(house)}>
        Это мой дом
      </Button>
    )}
  </>
);

export const HouseSheet = ({
  place,
  canPick,
  isAdding,
  addError,
  onChoose,
  onAdd,
  onClose,
}: HouseSheetProps) => (
  <section className={styles.Sheet} aria-live="polite">
    <IconButton
      size="medium"
      variant="ghost"
      aria-label="Закрыть"
      className={styles.Close}
      onClick={onClose}
    >
      <Icon src={closeIcon} size={20} />
    </IconButton>

    <Flex direction="column" align="stretch" gapY={12}>
      {place.kind === "loading" && (
        <Flex align="center" gap={12} className={styles.Line}>
          <Spinner size={20} />
          <Secondary>Ищем дом…</Secondary>
        </Flex>
      )}

      {place.kind === "error" && (
        <>
          <Title>Не получилось загрузить дом</Title>
          <Secondary>
            {errorMessage(place.error, "Проверьте связь и попробуйте ещё раз")}
          </Secondary>
          <Button size="medium" variant="secondary" onClick={place.retry}>
            Повторить
          </Button>
        </>
      )}

      {place.kind === "house" && (
        <HouseDetails
          house={place.house}
          canPick={canPick}
          onChoose={onChoose}
        />
      )}

      {place.kind === "address" && (
        <>
          <Flex direction="column" align="stretch" gapY={4}>
            <Title>{place.address}</Title>
            <Secondary>Этого дома пока нет в справочнике</Secondary>
          </Flex>
          {canPick && (
            <Button size="large" stretched loading={isAdding} onClick={onAdd}>
              Добавить дом и выбрать
            </Button>
          )}
          {addError != null && (
            <Typography.Text variant="description" className={styles.Error}>
              {errorMessage(addError, "Не получилось добавить дом")}
            </Typography.Text>
          )}
        </>
      )}

      {place.kind === "geocoder_failed" && (
        <Typography.Text variant="body" color="primary" className={styles.Line}>
          Не удалось определить адрес. Попробуйте ещё раз
        </Typography.Text>
      )}

      {place.kind === "nothing" && (
        <Typography.Text variant="body" color="primary" className={styles.Line}>
          Здесь нет дома с номером
        </Typography.Text>
      )}
    </Flex>
  </section>
);
