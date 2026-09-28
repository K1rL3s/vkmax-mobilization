import { Button, CellSimple, Flex, Panel, Typography } from "@maxhub/max-ui";
import { useQuery } from "@tanstack/react-query";
import { generatePath, Link, Navigate, useNavigate } from "react-router-dom";

import {
  confirmationLabel,
  confirmationTone,
  residencyState,
  type ResidencyState,
} from "@/features/flat-confirmation";
import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { useSession, workingOrgs } from "@/shared/model/session";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import {
  alertIcon,
  buildingIcon,
  bulbIcon,
  clockIcon,
  homeIcon,
  Icon,
  infoIcon,
  trashIcon,
} from "@/shared/ui/icon";
import { StatusPill } from "@/shared/ui/status-pill";

import { PhonePanel } from "./phone-panel";
import { useForgetMe } from "./use-forget-me";
import {
  ALWAYS_DELIVERED,
  CATEGORIES,
  LEVEL_LABEL,
  settingsQueryOptions,
} from "./use-notification-settings";

import styles from "./profile.module.css";

const WARNING: Partial<
  Record<ResidencyState, { title: string; action: string; alert: boolean }>
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
  const forgetMe = useForgetMe();

  if (!residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  const orgs = workingOrgs(session);

  const enterAdmin = async (orgId: number) => {
    await selectOrg(orgId);
    selectCabinet("admin");
    await navigate(Routes.ADMIN);
  };

  const state = residencyState(residency);
  const warning = WARNING[state];

  return (
    <Panel className={styles.Page} mode="secondary">
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
                <Flex align="center" gap={8} wrap="wrap">
                  {residency.flat_number && `кв. ${residency.flat_number}`}
                  <StatusPill tone={confirmationTone(state)}>
                    {confirmationLabel(state)}
                  </StatusPill>
                </Flex>
              }
              showChevron
              onClick={() => void navigate(Routes.FLAT)}
            />
          </div>
        </section>
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
                  innerClassNames={{ title: styles.CellTitle }}
                  title={
                    <Flex align="center" gap={8}>
                      <span className={styles.Ellipsis}>{org.name}</span>
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

      <PhonePanel />

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
              subtitle="Заявки, показания, опросы, права жильца и бот"
              showChevron
              onClick={() => void navigate(Routes.FAQ)}
            />
            <CellSimple
              separator
              before={<Icon src={trashIcon} className={styles.CellIcon} />}
              title="Удалить мои данные"
              subtitle="Заявки и показания останутся без вашего имени"
              showChevron
              onClick={forgetMe.ask}
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

      <ConfirmDialog
        isOpen={forgetMe.isOpen}
        title="Удалить мои данные?"
        description="Удалятся имя, привязки к домам и квартирам, подтверждение квартиры, роли в УК, настройки уведомлений и согласие. Заявки с фото и перепиской, показания и голоса в опросах останутся у УК без вашего имени. Чтобы вернуться, откройте приложение заново и дайте согласие."
        confirmLabel="Удалить"
        error={forgetMe.error}
        isPending={forgetMe.isPending}
        onConfirm={forgetMe.submit}
        onClose={forgetMe.cancel}
      />
    </Panel>
  );
};

export const Component = ProfilePage;
