import {
  Button,
  CellSimple,
  Flex,
  Panel,
  Tappable,
  Typography,
} from "@maxhub/max-ui";
import { useQuery } from "@tanstack/react-query";
import { generatePath, Link, Navigate, useNavigate } from "react-router-dom";

import {
  confirmationCaption,
  confirmationView,
  type ConfirmationView,
} from "@/features/flat-confirmation";
import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { useSession, workingOrgs } from "@/shared/model/session";
import { Chevron } from "@/shared/ui/chevron";
import {
  alertIcon,
  buildingIcon,
  bulbIcon,
  clockIcon,
  homeIcon,
  Icon,
  infoIcon,
} from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { StatusPill } from "@/shared/ui/status-pill";

import {
  ALWAYS_DELIVERED,
  CATEGORIES,
  LEVEL_LABEL,
  settingsQueryOptions,
} from "./use-notification-settings";

import styles from "./profile.module.css";

const WARNING: Record<
  Exclude<ConfirmationView, "verified" | "no-flat">,
  { title: string; action: string; alert: boolean }
> = {
  ways: {
    title: "Квартира не подтверждена",
    action: "Подтвердить квартиру",
    alert: true,
  },
  pending: {
    title: "Запрос на подтверждение у УК",
    action: "Открыть запрос",
    alert: false,
  },
  rejected: {
    title: "УК отклонила запрос",
    action: "Подтвердить ещё раз",
    alert: true,
  },
};

const ProfilePage = () => {
  const navigate = useNavigate();
  const {
    session,
    currentResidency: residency,
    selectCabinet,
    selectOrg,
  } = useSession();
  const notifications = useQuery(settingsQueryOptions());

  if (!residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  const orgs = workingOrgs(session);

  const enterAdmin = async (orgId: number) => {
    await selectOrg(orgId);
    selectCabinet("admin");
    await navigate(Routes.ADMIN);
  };

  const view = confirmationView(residency);
  const warning =
    residency.is_connected && view !== "verified" && view !== "no-flat"
      ? WARNING[view]
      : null;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex asChild align="center" gap={12}>
        <Tappable
          className={styles.Summary}
          onClick={() => void navigate(Routes.RESIDENCIES)}
        >
          <IconTile icon={homeIcon} tone="card" size="large" />
          <Flex
            className={styles.Grow}
            align="stretch"
            direction="column"
            gapY={2}
          >
            <Typography.Text variant="title" color="primary">
              {residency.address}
              {residency.flat_number && `, кв. ${residency.flat_number}`}
            </Typography.Text>
            {!warning && (
              <Typography.Text variant="description" color="secondary">
                {residency.is_connected
                  ? confirmationCaption(residency)
                  : "дом ещё не подключён к сервису"}
              </Typography.Text>
            )}
            <Typography.Text variant="description" color="primary">
              Сменить дом
            </Typography.Text>
          </Flex>
          <Chevron />
        </Tappable>
      </Flex>

      {warning && (
        <Flex align="stretch" direction="column" gap={8}>
          <Flex
            align="center"
            gap={8}
            className={cn(styles.Warning, warning.alert && styles.alert)}
          >
            <Icon
              src={warning.alert ? alertIcon : clockIcon}
              size={20}
              className={styles.WarningIcon}
            />
            <Typography.Text variant="body-strong" color="primary">
              {warning.title}
            </Typography.Text>
          </Flex>
          <Typography.Text variant="description" color="secondary">
            После подтверждения станут доступны начисления и счётчики
          </Typography.Text>
          <Button asChild size="medium" variant="secondary" stretched>
            <Link
              to={generatePath(Routes.FLAT_CONFIRMATION, {
                residentId: String(residency.resident_id),
              })}
              state={{ returnTo: Routes.PROFILE }}
            >
              {warning.action}
            </Link>
          </Button>
        </Flex>
      )}

      {orgs.length > 0 && (
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Работа</h2>
            </Typography.Text>
            <div className={styles.Panel}>
              {orgs.map((org, index) => (
                <CellSimple
                  key={org.org_id}
                  separator={index > 0}
                  before={
                    <Icon src={buildingIcon} className={styles.CellIcon} />
                  }
                  innerClassNames={{ title: styles.OrgTitle }}
                  title={
                    <Flex align="center" gap={8}>
                      <span className={styles.OrgName}>{org.name}</span>
                      {org.is_demo && (
                        <StatusPill tone="themed">демо</StatusPill>
                      )}
                    </Flex>
                  }
                  subtitle="Кабинет УК"
                  showChevron
                  onClick={() => void enterAdmin(org.org_id)}
                />
              ))}
            </div>
          </section>
        </Flex>
      )}

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Мой дом</h2>
          </Typography.Text>
          <div className={styles.Panel}>
            <CellSimple
              before={<Icon src={buildingIcon} className={styles.CellIcon} />}
              title="Карточка дома"
              subtitle="УК, тарифы, капремонт, документы"
              showChevron
              onClick={() => void navigate(Routes.HOUSE_CARD)}
            />
            <CellSimple
              separator
              before={<Icon src={homeIcon} className={styles.CellIcon} />}
              title="Моя квартира"
              subtitle={
                warning
                  ? "Доступна после подтверждения квартиры"
                  : "Начисления, счётчики, код арендатору"
              }
              showChevron
              onClick={() => void navigate(Routes.FLAT)}
            />
          </div>
        </section>
      </Flex>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Уведомления</h2>
          </Typography.Text>
          <div className={styles.Panel}>
            {CATEGORIES.map(({ category, title, icon }, index) => {
              const level = notifications.data?.settings.find(
                (item) => item.category === category,
              )?.level;
              const label = notifications.isError
                ? "Не удалось загрузить"
                : level && LEVEL_LABEL[level];

              return (
                <CellSimple
                  key={category}
                  separator={index > 0}
                  before={<Icon src={icon} className={styles.CellIcon} />}
                  title={title}
                  after={
                    label && (
                      <Typography.Text
                        variant="body"
                        color="secondary"
                        className={styles.Level}
                      >
                        {label}
                      </Typography.Text>
                    )
                  }
                  showChevron
                  onClick={() => void navigate(Routes.NOTIFICATIONS)}
                />
              );
            })}
          </div>
          <Typography.Text variant="description" color="tertiary">
            {ALWAYS_DELIVERED}
          </Typography.Text>
        </section>
      </Flex>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Помощь</h2>
          </Typography.Text>
          <div className={styles.Panel}>
            <CellSimple
              before={<Icon src={bulbIcon} className={styles.CellIcon} />}
              title="Как это работает"
              subtitle="Заявки, показания, собрания и что умеет бот в чате"
              showChevron
              onClick={() => void navigate(Routes.FAQ)}
            />
          </div>
        </section>
      </Flex>

      <Flex align="center" gap={12} className={styles.Note}>
        <Icon src={infoIcon} size={20} className={styles.NoteIcon} />
        <Typography.Text variant="description" color="secondary">
          Начисления, квитанции, документы и лицевые счета - модельные данные
          для демонстрации
        </Typography.Text>
      </Flex>
    </Panel>
  );
};

export const Component = ProfilePage;
