import type { ReactNode } from "react";
import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";

import { useHouseCard } from "@/features/house";
import { useSession } from "@/shared/model/session";
import { Card } from "@/shared/ui/card";
import { alertIcon, flameIcon, infoIcon, wrenchIcon } from "@/shared/ui/icon";
import { IconTile, type IconTileTone } from "@/shared/ui/icon-tile";

import { emergencyContact } from "./emergency-contact";

import styles from "./emergency.module.css";

const Block = ({
  icon,
  tone,
  title,
  children,
}: {
  icon: string;
  tone: IconTileTone;
  title: string;
  children: ReactNode;
}) => (
  <Card>
    <Flex align="center" gap={12}>
      <IconTile icon={icon} tone={tone} />
      <Typography.Text
        asChild
        variant="title"
        color="primary"
        className={styles.Grow}
      >
        <h2>{title}</h2>
      </Typography.Text>
    </Flex>
    {children}
  </Card>
);

const Call = ({
  phone,
  children,
  destructive,
}: {
  phone: string;
  children: ReactNode;
  destructive?: boolean;
}) => (
  <Button
    asChild
    size="large"
    stretched
    variant={destructive ? "destructive" : "secondary"}
  >
    <a href={`tel:${phone}`}>{children}</a>
  </Button>
);

const EmergencyPage = () => {
  const { currentResidency: residency } = useSession();
  const card = useHouseCard(residency?.house_id);
  const contact = emergencyContact(card.data?.org);

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text variant="body" color="secondary">
        Сначала позвоните, заявку можно оформить после звонка
      </Typography.Text>

      <Block icon={flameIcon} tone="negative" title="Угроза жизни, пожар, дым">
        <Typography.Text variant="body" color="primary">
          Выйдите из квартиры и закройте дверь, не пользуйтесь лифтом
        </Typography.Text>
        <Call phone="112" destructive>
          Позвонить 112
        </Call>
      </Block>

      <Block icon={alertIcon} tone="negative" title="Запах газа">
        <Typography.Text variant="body" color="primary">
          Не включайте свет и приборы, не зажигайте огонь, откройте окна.
          Выйдите и звоните не из квартиры
        </Typography.Text>
        <Call phone="104">Позвонить 104</Call>
      </Block>

      <Block icon={wrenchIcon} tone="themed" title="Авария в доме">
        <Typography.Text variant="body" color="primary">
          Течёт вода - перекройте кран на стояке или под раковиной. Искрит
          проводка или пахнет гарью - отключите автомат в щитке, если это
          безопасно
        </Typography.Text>
        {contact?.isEmergencyLine && (
          <>
            <Call phone={contact.phone}>Аварийная служба: {contact.phone}</Call>
            <Typography.Text variant="description" color="secondary">
              Оператор обязан ответить за 5 минут
            </Typography.Text>
          </>
        )}
        {!contact?.isEmergencyLine && (
          <Typography.Text variant="description" color="secondary">
            Номер аварийной службы есть в квитанции и на доске объявлений в
            подъезде
          </Typography.Text>
        )}
        {contact && !contact.isEmergencyLine && (
          <Call phone={contact.phone}>Телефон УК: {contact.phone}</Call>
        )}
      </Block>

      <Block icon={infoIcon} tone="neutral" title="Что сказать диспетчеру">
        <Typography.Text asChild variant="body" color="primary">
          <ul className={styles.Steps}>
            <li>Адрес, подъезд, этаж и номер квартиры</li>
            <li>Что случилось и когда началось</li>
            <li>Есть ли угроза людям и соседям снизу</li>
            <li>
              Запишите время звонка и номер заявки, который назовёт диспетчер
            </li>
          </ul>
        </Typography.Text>
      </Block>
    </Panel>
  );
};

export const Component = EmergencyPage;
