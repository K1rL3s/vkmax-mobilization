import { useState } from "react";
import { Button, CellSimple, Flex, Panel, Typography } from "@maxhub/max-ui";
import { useQuery } from "@tanstack/react-query";
import { generatePath, Link, Navigate, useNavigate } from "react-router-dom";

import {
  confirmationLabel,
  confirmationTone,
  residencyState,
  type ResidencyState,
} from "@/features/flat-confirmation";
import { HandoverDialog } from "@/features/chairman-handover";
import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { useSession, workingOrgs } from "@/shared/model/session";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import {
  alertIcon,
  bellIcon,
  buildingIcon,
  bulbIcon,
  clockIcon,
  homeIcon,
  Icon,
  infoIcon,
  textSizeIcon,
  trashIcon,
  usersIcon,
} from "@/shared/ui/icon";
import { StatusPill } from "@/shared/ui/status-pill";

import { PhonePanel } from "./phone-panel";
import { useForgetMe } from "./use-forget-me";
import { settingsQueryOptions } from "./use-notification-settings";

import styles from "./profile.module.css";

const WARNING: Partial<
  Record<ResidencyState, { title: string; action: string; alert: boolean }>
> = {
  ways: {
    title: "Квартира не подтверждена",
    action: "Подтвердить",
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
  const [handoverOpen, setHandoverOpen] = useState(false);

  if (!residency) {
    return forgetMe.isOpen ? null : <Navigate to={Routes.HOME} replace />;
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
            {residency.is_chairman && (
              <CellSimple
                separator
                before={<Icon src={usersIcon} className={styles.CellIcon} />}
                title="Передать роль председателя"
                subtitle="Ссылка соседу, действует 48 часов"
                showChevron
                onClick={() => setHandoverOpen(true)}
              />
            )}
          </div>
        </section>
      </Flex>

      {warning && (
        <Flex
          align="stretch"
          direction="column"
          gap={12}
          className={styles.Warning}
        >
          <Flex align="stretch" direction="column" gapY={4}>
            <Flex align="center" gap={8}>
              <Icon
                src={warning.alert ? alertIcon : clockIcon}
                size={20}
                className={cn(
                  styles.WarningIcon,
                  warning.alert && styles.alert,
                )}
              />
              <Typography.Text variant="body-strong" color="primary">
                {warning.title}
              </Typography.Text>
            </Flex>
            <Typography.Text variant="description" color="secondary">
              После подтверждения станут доступны начисления и счётчики
            </Typography.Text>
          </Flex>
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

      <div className={styles.Panel}>
        <CellSimple
          before={<Icon src={bellIcon} className={styles.CellIcon} />}
          title="Уведомления и звук"
          after={
            notifications.isError && (
              <span
                role="img"
                aria-label="Не удалось загрузить настройки"
                className={styles.Attention}
              >
                !
              </span>
            )
          }
          showChevron
          onClick={() => void navigate(Routes.NOTIFICATIONS)}
        />
      </div>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Экран</h2>
          </Typography.Text>
          <div className={styles.Panel}>
            <CellSimple
              before={<Icon src={textSizeIcon} className={styles.CellIcon} />}
              title="Размер текста"
              subtitle="Обычный, крупный или очень крупный"
              showChevron
              onClick={() => void navigate(Routes.APPEARANCE)}
            />
          </div>
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

      {residency.is_chairman && (
        <HandoverDialog
          houseId={residency.house_id}
          address={residency.address}
          isOpen={handoverOpen}
          onClose={() => setHandoverOpen(false)}
        />
      )}
    </Panel>
  );
};

export const Component = ProfilePage;
