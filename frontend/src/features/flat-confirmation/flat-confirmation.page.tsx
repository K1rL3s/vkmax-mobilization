import type { ReactNode } from "react";
import { Button, Typography } from "@maxhub/max-ui";
import { Navigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import {
  alertIcon,
  checkIcon,
  clockIcon,
  homeIcon,
  infoIcon,
} from "@/shared/ui/icon";

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

  const hero = (
    <ConfirmationHero
      icon={homeIcon}
      tone="themed"
      title="Подтвердите квартиру"
      address={address}
    />
  );

  if (view === "no-flat") {
    return (
      <PageLayout footer={later}>
        {hero}

        <Notice
          icon={infoIcon}
          tone="info"
          title="УК ещё не добавила вашу квартиру"
          text="Квартира указана номером, но её пока нет в данных управляющей компании. Подтвердить её сейчас нельзя"
        />
      </PageLayout>
    );
  }

  return (
    <PageLayout footer={later}>
      {hero}

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
