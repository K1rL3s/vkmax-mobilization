import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { QRCodeSVG } from "qrcode.react";
import { z } from "zod";

import { rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";
import { qrIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import styles from "./admin-house-qr.module.css";

const AdminHouseQrPage = () => {
  const params = useRouteParams(
    z.object({ houseId: z.coerce.number().int().positive() }),
  );

  const card = rqClient.useQuery(
    "get",
    "/api/admin/houses/{house_id}",
    { params: { ...orgParams(), path: { house_id: params?.houseId ?? 0 } } },
    { enabled: params !== null },
  );

  if (params === null) {
    return (
      <EmptyState
        fill
        icon={qrIcon}
        title="Дом не найден"
        description="Откройте QR-коды из карточки дома"
      />
    );
  }

  if (card.isPending) {
    return <LoadingState fill title="Готовим QR-коды" />;
  }

  if (card.isError) {
    return (
      <ErrorState error={card.error} fill onRetry={() => void card.refetch()} />
    );
  }

  const house = card.data;

  if (house.entrance_qrs.length === 0) {
    return (
      <EmptyState
        fill
        icon={qrIcon}
        title="Подъездов нет"
        description="У дома не указано число подъездов, поэтому и печатать нечего"
      />
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Screen}>
        <Flex align="stretch" direction="column" gapY={4}>
          <Typography.Text asChild variant="title" color="primary">
            <h1>Подъездные QR-коды</h1>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            Распечатайте и повесьте у входа в каждый подъезд: по коду жители
            сразу попадают в свой дом и привязывают квартиру. На листе A4 по
            одному подъезду
          </Typography.Text>
        </Flex>

        <Button size="large" stretched onClick={() => window.print()}>
          Распечатать
        </Button>
      </div>

      {house.entrance_qrs.map((qr) => (
        <section key={qr.entrance} className={styles.Sheet}>
          <QRCodeSVG
            className={styles.Code}
            value={qr.deeplink}
            marginSize={2}
            title={`QR-код подъезда ${qr.entrance}`}
          />

          <h2 className={styles.Entrance}>Подъезд {qr.entrance}</h2>

          <p className={styles.Address}>{house.address}</p>

          <p className={styles.Hint}>
            Наведите камеру телефона на код и откройте ссылку в MAX: бот сразу
            откроет этот дом, останется выбрать номер квартиры
          </p>
        </section>
      ))}
    </Panel>
  );
};

export const Component = AdminHouseQrPage;
