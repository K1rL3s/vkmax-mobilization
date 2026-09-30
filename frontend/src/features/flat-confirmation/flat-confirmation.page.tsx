import type { ReactNode } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";
import { Link, Navigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import {
  alertIcon,
  checkIcon,
  clockIcon,
  homeIcon,
  infoIcon,
} from "@/shared/ui/icon";

import { changeFlatLink } from "./domain/change-flat";
import { useFlatConfirmation } from "./model/use-flat-confirmation";
import { ConfirmationHero } from "./ui/confirmation-hero";
import { Notice } from "./ui/notice";
import { UnlockedList } from "./ui/unlocked-list";
import { WaysPanel } from "./ui/ways-panel";

import styles from "./flat-confirmation.module.css";

type PageLayoutProps = {
  children: ReactNode;
  footer: ReactNode;
};

const PageLayout = ({ children, footer }: PageLayoutProps) => (
  <div className={styles.Page}>
    <div className={styles.Content}>{children}</div>
    <div className={styles.Footer}>{footer}</div>
  </div>
);

const FlatConfirmationPage = () => {
  const confirmation = useFlatConfirmation();

  if (!confirmation.residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  const { residency, view, address, returnTo, exit } = confirmation;

  const done = (
    <Button size="large" stretched onClick={exit}>
      Готово
    </Button>
  );

  if (view === "verified") {
    return (
      <PageLayout footer={done}>
        <ConfirmationHero
          icon={checkIcon}
          tone="positive"
          title="Квартира подтверждена"
          address={address}
        />

        <UnlockedList />
      </PageLayout>
    );
  }

  if (view === "pending") {
    return (
      <PageLayout footer={done}>
        <ConfirmationHero
          icon={clockIcon}
          tone="themed"
          title="Запрос отправлен в УК"
          address={address}
        />

        <Typography.Text variant="description" color="secondary">
          Ответ придёт в чат. Пока запрос на рассмотрении, подтверждение
          открывается на этом экране
        </Typography.Text>
      </PageLayout>
    );
  }

  const later = (
    <Button size="large" stretched variant="secondary" onClick={exit}>
      Позже
    </Button>
  );

  if (view === "no-flat" || view === "flat-missing") {
    const isMissing = view === "flat-missing";

    return (
      <PageLayout
        footer={
          <Flex align="stretch" direction="column" gapY={8}>
            <Button asChild size="large" stretched>
              <Link {...changeFlatLink(residency, returnTo)} replace>
                {isMissing ? "Изменить номер квартиры" : "Указать квартиру"}
              </Link>
            </Button>
            {later}
          </Flex>
        }
      >
        <ConfirmationHero
          icon={homeIcon}
          tone="themed"
          title="Подтвердить пока нельзя"
          address={address}
        />

        <Notice
          icon={infoIcon}
          tone="info"
          title={
            isMissing
              ? "УК ещё не добавила вашу квартиру"
              : "Квартира не указана"
          }
          text={
            isMissing
              ? "Квартиры с этим номером пока нет в данных управляющей компании. Если номер указан с ошибкой, исправьте его"
              : "Укажите номер квартиры - без него подтвердить её не получится"
          }
        />
      </PageLayout>
    );
  }

  return (
    <PageLayout footer={later}>
      <ConfirmationHero
        icon={homeIcon}
        tone="themed"
        title="Подтвердите квартиру"
        address={address}
      />

      {view === "rejected" ? (
        <Notice
          icon={alertIcon}
          tone="alert"
          title="Запрос отклонён"
          text={[
            residency.verification_reject_reason,
            "Проверьте лицевой счёт или отправьте запрос ещё раз",
          ]
            .filter(Boolean)
            .join(". ")}
        />
      ) : (
        <Typography.Text asChild variant="body" color="primary">
          <p className={styles.Why}>
            Счётчики и начисления открываются только жителям с подтверждённой
            квартирой
          </p>
        </Typography.Text>
      )}

      <WaysPanel residentId={residency.resident_id} returnTo={returnTo} />
    </PageLayout>
  );
};

export const Component = FlatConfirmationPage;
