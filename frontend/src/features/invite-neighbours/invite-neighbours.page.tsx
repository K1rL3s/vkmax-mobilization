import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { QRCodeSVG } from "qrcode.react";
import { Navigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import { useNeighbourInvite } from "./use-neighbour-invite";

import styles from "./invite-neighbours.module.css";

const InviteNeighboursPage = () => {
  const { currentResidency: residency } = useSession();
  const {
    invite,
    subtitle,
    share,
    sendLeaflet,
    isSendingLeaflet,
    isLeafletSent,
    leafletLabel,
    leafletError,
  } = useNeighbourInvite(residency?.house_id);

  if (!residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  if (invite.isPending) {
    return <LoadingState fill title="Готовим ссылку в дом" />;
  }

  if (invite.isError) {
    return (
      <ErrorState
        error={invite.error}
        fill
        onRetry={() => void invite.refetch()}
      />
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="header" color="primary">
          <h1>Позвать соседей</h1>
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {subtitle}
        </Typography.Text>
      </Flex>

      <div className={styles.Sheet}>
        <QRCodeSVG
          className={styles.Code}
          value={invite.data.link}
          marginSize={2}
          title={`QR-код ссылки в дом ${invite.data.address}`}
        />
        <p className={styles.Address}>{invite.data.address}</p>
      </div>

      <Flex align="stretch" direction="column" gapY={8}>
        <Button size="large" stretched onClick={share}>
          Поделиться
        </Button>
        <Button
          size="large"
          variant="secondary"
          stretched
          loading={isSendingLeaflet}
          disabled={isLeafletSent}
          onClick={sendLeaflet}
        >
          {leafletLabel}
        </Button>
        {leafletError && (
          <Typography.Text variant="description" className={styles.Failed}>
            {leafletError}
          </Typography.Text>
        )}
      </Flex>

      <Typography.Text variant="description" color="secondary">
        Ссылка постоянная и ведёт в этот дом. Номер квартиры каждый сосед
        указывает сам
      </Typography.Text>
    </Panel>
  );
};

export const Component = InviteNeighboursPage;
