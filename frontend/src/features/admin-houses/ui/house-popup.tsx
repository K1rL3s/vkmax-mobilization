import type { ReactNode } from "react";
import { Flex, IconButton, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, type To, useNavigate } from "react-router-dom";

import { formatDay, formatPercent, plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { closeIcon, Icon } from "@/shared/ui/icon";
import { TONE_COLORS } from "@/shared/ui/map";
import { StatusPill } from "@/shared/ui/status-pill";

import { STATES } from "../domain/map-filters";
import type { AdminMapHouse } from "../model/use-admin-map";
import type { PlatformHouse } from "../model/use-platform-map";

import styles from "./house-popup.module.css";

const rating = (value: number) =>
  (value / 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 });

const Card = ({
  title,
  badge,
  onClose,
  children,
}: {
  title: string;
  badge: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) => (
  <section className={styles.HousePopup} aria-label={title}>
    <div className={styles.Head}>
      <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h2 className={styles.Title}>{title}</h2>
        </Typography.Text>
        {badge}
      </Flex>
      <IconButton
        className={styles.Close}
        size="small"
        variant="secondary"
        aria-label="Закрыть"
        onClick={onClose}
      >
        <Icon src={closeIcon} size={20} />
      </IconButton>
    </div>
    <div className={styles.Rows}>{children}</div>
  </section>
);

const Row = ({
  to,
  onClick,
  children,
}: {
  to?: To;
  onClick?: () => void;
  children: ReactNode;
}) => {
  const navigate = useNavigate();
  const action =
    onClick ?? (to === undefined ? undefined : () => void navigate(to));
  const text = (
    <Typography.Text className={styles.Grow} variant="body" color="primary">
      {children}
    </Typography.Text>
  );

  return action ? (
    <Tappable className={styles.Row} onClick={action}>
      {text}
      <Chevron />
    </Tappable>
  ) : (
    <div className={styles.Row}>{text}</div>
  );
};

export const HousePopup = ({
  house,
  isAdmin,
  onClose,
}: {
  house: AdminMapHouse;
  isAdmin: boolean;
  onClose: () => void;
}) => {
  const state = STATES.find((item) => item.id === house.state) ?? STATES[4];
  const houseSearch = `?house=${house.id}`;
  const card = generatePath(Routes.ADMIN_HOUSE, { houseId: String(house.id) });
  const requests = [
    house.open > 0 && `открыто ${house.open}`,
    house.emergency > 0 && `аварий ${house.emergency}`,
    house.escalated > 0 && `эскалация ${house.escalated}`,
    house.overdue > 0 && `просрочено ${house.overdue}`,
    house.grouped > 0 && `групповых ${house.grouped}`,
  ].filter(Boolean);
  const urgent = house.urgent_text ?? "";

  return (
    <Card
      title={house.address}
      badge={
        <span className={styles.State}>
          <span
            className={styles.Dot}
            style={{ backgroundColor: TONE_COLORS[state.tone] }}
          />
          <Typography.Text variant="description" color="secondary">
            {state.label}
          </Typography.Text>
        </span>
      }
      onClose={onClose}
    >
      <Row
        to={{
          pathname: Routes.ADMIN_REQUESTS,
          search: `${houseSearch}${house.overdue > 0 ? "&filter=overdue" : ""}`,
        }}
      >
        {requests.length > 0
          ? `Заявки: ${requests.join(" · ")}`
          : "Заявки: открытых нет"}
      </Row>

      {house.urgent_id != null && (
        <Row to={{ pathname: Routes.ADMIN_ANNOUNCEMENTS, search: houseSearch }}>
          Срочное объявление:{" "}
          {urgent.length > 80 ? `${urgent.slice(0, 80)}…` : urgent}
        </Row>
      )}

      {house.poll_id != null && (
        <Row
          to={generatePath(Routes.ADMIN_POLL, {
            pollId: String(house.poll_id),
          })}
        >
          {house.poll_ends_at
            ? `Опрос до ${formatDay(house.poll_ends_at)}`
            : "Опрос"}
          {house.poll_turnout != null &&
            `: проголосовало ${formatPercent(house.poll_turnout)}`}
        </Row>
      )}

      {house.appointments_today > 0 && (
        <Row to={{ pathname: Routes.ADMIN_RECEPTION, search: houseSearch }}>
          Приём сегодня: {house.appointments_today}{" "}
          {plural(house.appointments_today, ["запись", "записи", "записей"])}
        </Row>
      )}

      {house.meters_percent != null && (
        <Row to={isAdmin ? card : undefined}>
          Счётчики: {Math.round(house.meters_percent / 100)}% квартир подали
          показания
        </Row>
      )}

      {house.rating != null && (
        <Row>Оценка жителей: {rating(house.rating)} из 5</Row>
      )}

      {isAdmin && house.residents_count != null && (
        <Row to={card}>
          Жителей {house.residents_count} из {house.flats_count}{" "}
          {plural(house.flats_count, ["квартиры", "квартир", "квартир"])} ·
          подтверждено {house.verified_residents ?? 0}
        </Row>
      )}

      {isAdmin && (house.pending_verifications ?? 0) > 0 && (
        <Row
          to={{
            pathname: Routes.ADMIN_VERIFICATIONS,
            search: `?house_id=${house.id}`,
          }}
        >
          Ждут проверки: {house.pending_verifications}
        </Row>
      )}

      {isAdmin && house.chat_bound != null && (
        <Row to={card}>{house.chat_bound ? "Чат привязан" : "Без чата"}</Row>
      )}
    </Card>
  );
};

export const PlatformHousePopup = ({
  house,
  onClose,
}: {
  house: PlatformHouse;
  onClose: () => void;
}) => (
  <Card
    title={house.address}
    badge={
      <Flex align="center" gap={6} wrap="wrap">
        <Typography.Text variant="description" color="secondary">
          {house.org_name ?? "УК не указана"}
        </Typography.Text>
        {house.is_demo && <StatusPill tone="themed">демо</StatusPill>}
      </Flex>
    }
    onClose={onClose}
  >
    <Row>
      {house.kind === "connected"
        ? "УК подключена к платформе"
        : house.kind === "added"
          ? "Дом добавлен жителем, УК не подключена"
          : "Дом пока не подключён к платформе"}
    </Row>

    {house.kind === "connected" && (
      <Row>
        {house.on_time_share != null || house.rating != null
          ? [
              house.on_time_share != null &&
                `В срок ${formatPercent(house.on_time_share)} заявок`,
              house.rating != null && `оценка ${rating(house.rating)} из 5`,
            ]
              .filter(Boolean)
              .join(" · ")
          : "Статистики пока нет: мало закрытых заявок"}
      </Row>
    )}

    {house.demand_count > 0 && (
      <Row>Ждут подключения: {house.demand_count}</Row>
    )}
  </Card>
);

export const StackPopup = ({
  houses,
  onChoose,
  onClose,
}: {
  houses: { id: number; address: string }[];
  onChoose: (id: number) => void;
  onClose: () => void;
}) => (
  <Card
    title={`В этой точке ${houses.length} ${plural(houses.length, ["дом", "дома", "домов"])}`}
    badge={null}
    onClose={onClose}
  >
    {houses.map((house) => (
      <Row key={house.id} onClick={() => onChoose(house.id)}>
        {house.address}
      </Row>
    ))}
  </Card>
);
