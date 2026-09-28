import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { z } from "zod";

import type { components } from "@/shared/api/schema/generated";

import { rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";
import { qrIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import styles from "./admin-house-qr.module.css";

type ObjectCategory = components["schemas"]["ObjectQr"]["category"];

type QrKind = "entrances" | ObjectCategory;

const KINDS: { kind: QrKind; label: string }[] = [
  { kind: "entrances", label: "Подъезды" },
  { kind: "elevator", label: "Лифты" },
  { kind: "electricity", label: "Свет" },
  { kind: "entrance", label: "Уборка" },
];

const OBJECT_SHEET: Partial<
  Record<ObjectCategory, { title: string; hint: string }>
> = {
  elevator: {
    title: "Лифт",
    hint: "Сломался лифт? Наведите камеру, заявка откроется в MAX",
  },
  electricity: {
    title: "Свет",
    hint: "Не горит свет? Наведите камеру, заявка откроется в MAX",
  },
  entrance: {
    title: "Уборка",
    hint: "Грязно в подъезде? Наведите камеру, заявка откроется в MAX",
  },
};

const AdminHouseQrPage = () => {
  const [kind, setKind] = useState<QrKind>("entrances");
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
            <h1>QR-коды дома</h1>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            {kind === "entrances"
              ? "Повесьте у входа в каждый подъезд: по коду жители сразу попадают в свой дом и привязывают квартиру"
              : "Повесьте на объект: по коду житель сразу открывает заявку с нужной категорией и подъездом"}
            . На листе A4 по одному подъезду
          </Typography.Text>
        </Flex>

        <div className={styles.Chips}>
          {KINDS.map((item) => (
            <Button
              key={item.kind}
              size="small"
              variant={item.kind === kind ? "primary" : "secondary"}
              aria-pressed={item.kind === kind}
              onClick={() => setKind(item.kind)}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <Button size="large" stretched onClick={() => window.print()}>
          Распечатать
        </Button>
      </div>

      {kind !== "entrances" &&
        house.object_qrs
          .filter((qr) => qr.category === kind)
          .map((qr) => (
            <section key={qr.entrance} className={styles.Sheet}>
              <QRCodeSVG
                className={styles.Code}
                value={qr.deeplink}
                marginSize={2}
                title={`QR-код: ${OBJECT_SHEET[kind]?.title ?? ""}, подъезд ${qr.entrance}`}
              />

              <h2 className={styles.Entrance}>
                {OBJECT_SHEET[kind]?.title} · подъезд {qr.entrance}
              </h2>

              <p className={styles.Address}>{house.address}</p>

              <p className={styles.Hint}>{OBJECT_SHEET[kind]?.hint}</p>
            </section>
          ))}

      {kind === "entrances" &&
        house.entrance_qrs.map((qr) => (
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
