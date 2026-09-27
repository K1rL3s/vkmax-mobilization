import type { ReactNode } from "react";
import { Button, CellSimple, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link, Navigate } from "react-router-dom";

import { MyAppointmentsSection } from "@/features/appointments";
import { type HouseCard, useHouseCard } from "@/features/house";
import { cn } from "@/shared/lib/css";
import { formatArea } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";
import {
  buildingIcon,
  clockIcon,
  documentIcon,
  geoPinIcon,
  homeIcon,
  Icon,
  infoIcon,
  phoneIcon,
  wrenchIcon,
} from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { TariffsSection } from "./tariffs-section";

import styles from "./house-card.module.css";

type Work = NonNullable<HouseCard["overhaul"]>["works"][number];

const Section = ({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) => (
  <Flex asChild align="stretch" direction="column" gap={8}>
    <section>
      <Typography.Text asChild variant="title" color="primary">
        <h2>{title}</h2>
      </Typography.Text>
      {children}
    </section>
  </Flex>
);

const Facts = ({ house }: { house: HouseCard }) => {
  const facts: { label: string; value: string; wide?: boolean }[] = [];

  if (house.built_year != null) {
    facts.push({ label: "Год постройки", value: String(house.built_year) });
  }

  if (house.floors != null) {
    facts.push({ label: "Этажей", value: String(house.floors) });
  }

  facts.push({ label: "Подъездов", value: String(house.entrances) });

  if (house.area != null) {
    facts.push({ label: "Площадь дома", value: formatArea(house.area) });
  }

  if (house.cadastral_no) {
    facts.push({
      label: "Кадастровый номер",
      value: house.cadastral_no,
      wide: true,
    });
  }

  return (
    <div className={styles.Facts}>
      {facts.map((fact) => (
        <Flex
          key={fact.label}
          direction="column"
          gapY={2}
          className={cn(fact.wide && styles.wide)}
        >
          <Typography.Text variant="description" color="secondary">
            {fact.label}
          </Typography.Text>
          <Typography.Text variant="body-strong" color="primary">
            {fact.value}
          </Typography.Text>
        </Flex>
      ))}
    </div>
  );
};

const Org = ({ house }: { house: HouseCard }) => {
  const { org } = house;

  if (!org) {
    return (
      <EmptyState
        icon={buildingIcon}
        title="УК дома неизвестна"
        description="В реестре лицензий нет управляющей компании этого дома, поэтому её контактов здесь нет. Уточните их у председателя совета дома"
      />
    );
  }

  return (
    <>
      <div className={styles.Panel}>
        <CellSimple
          before={<Icon src={buildingIcon} className={styles.CellIcon} />}
          overline="Управляет домом"
          title={org.name}
          subtitle={org.license_no ? `Лицензия № ${org.license_no}` : undefined}
        />
        <CellSimple
          separator
          before={<Icon src={phoneIcon} className={styles.CellIcon} />}
          overline="Телефон"
          title={org.phone}
          showChevron
          asChild
        >
          <a href={`tel:${org.phone}`} />
        </CellSimple>
        <CellSimple
          separator
          before={<Icon src={geoPinIcon} className={styles.CellIcon} />}
          overline="Адрес офиса"
          title={org.address}
        />
        <CellSimple
          separator
          before={<Icon src={clockIcon} className={styles.CellIcon} />}
          overline="Режим приёма"
          title={org.reception_note ?? "УК не указала часы приёма"}
        />
      </div>

      {house.is_connected ? (
        <>
          <Button asChild size="large" stretched>
            <Link to={Routes.APPOINTMENTS}>Записаться на приём</Link>
          </Button>
          <MyAppointmentsSection timeZone={org.timezone} />
        </>
      ) : (
        <Typography.Text variant="description" color="secondary">
          УК ещё не подключилась к сервису, поэтому запись на приём, тарифы и
          документы здесь недоступны. По всем вопросам звоните в УК
        </Typography.Text>
      )}
    </>
  );
};

const Works = ({
  title,
  works,
  done,
}: {
  title: string;
  works: Work[];
  done: boolean;
}) => (
  <Flex direction="column" align="stretch" gapY={8} className={styles.Block}>
    <Typography.Text variant="description" color="secondary">
      {title}
    </Typography.Text>
    {works.map((work) => (
      <Flex key={`${work.year}-${work.title}`} align="center" gap={8}>
        <span className={cn(styles.Dot, done && styles.done)} />
        <Typography.Text variant="body" color="primary" className={styles.Grow}>
          {work.title}
        </Typography.Text>
        <Typography.Text variant="body" color="secondary">
          {work.year}
        </Typography.Text>
      </Flex>
    ))}
  </Flex>
);

const Overhaul = ({ overhaul }: { overhaul: HouseCard["overhaul"] }) => {
  if (!overhaul || (!overhaul.program && overhaul.works.length === 0)) {
    return (
      <EmptyState
        icon={wrenchIcon}
        title="Программы капремонта нет"
        description="Для дома пока не загружены данные региональной программы капитального ремонта"
      />
    );
  }

  const byYear = (a: Work, b: Work) => a.year - b.year;
  const upcoming = overhaul.works.filter((work) => !work.is_done).sort(byYear);
  const done = overhaul.works.filter((work) => work.is_done).sort(byYear);

  return (
    <div className={styles.Panel}>
      {overhaul.program && (
        <Flex direction="column" gapY={2} className={styles.Block}>
          <Typography.Text variant="description" color="secondary">
            Региональная программа
          </Typography.Text>
          <Typography.Text variant="body-strong" color="primary">
            {overhaul.program}
          </Typography.Text>
        </Flex>
      )}
      {upcoming.length > 0 && (
        <Works title="Ближайшие" works={upcoming} done={false} />
      )}
      {done.length > 0 && <Works title="Выполненные" works={done} done />}
    </div>
  );
};

const Documents = ({ house }: { house: HouseCard }) =>
  house.documents.length === 0 ? (
    <EmptyState
      icon={documentIcon}
      title="Документов пока нет"
      description={
        house.is_connected
          ? "УК ещё не выложила документы дома: договор управления, отчёты, решения собраний"
          : "Документы дома выкладывает УК, когда подключает дом к сервису"
      }
    />
  ) : (
    <div className={styles.Panel}>
      {house.documents.map((document, index) => (
        <CellSimple
          key={document.url}
          separator={index > 0}
          before={<Icon src={documentIcon} className={styles.CellIcon} />}
          title={document.name}
          showChevron
          asChild
        >
          <a href={document.url} target="_blank" rel="noreferrer" />
        </CellSimple>
      ))}
    </div>
  );

const HouseCardPage = () => {
  const { currentResidency: residency } = useSession();
  const card = useHouseCard(residency?.house_id);

  if (!residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  if (card.isPending) {
    return <LoadingState fill title="Загружаем карточку дома" />;
  }

  if (card.isError) {
    return (
      <ErrorState error={card.error} fill onRetry={() => void card.refetch()} />
    );
  }

  const house = card.data;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="center" gap={12}>
        <IconTile icon={homeIcon} tone="themed" size="large" />
        <Flex
          className={styles.Grow}
          align="stretch"
          direction="column"
          gapY={2}
        >
          <Typography.Text variant="title" color="primary">
            {house.address}
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            {house.region} · многоквартирный дом
          </Typography.Text>
        </Flex>
      </Flex>

      <Facts house={house} />

      <Section title="Управляющая компания">
        <Org house={house} />
      </Section>

      <TariffsSection houseId={house.id} isConnected={house.is_connected} />

      <Section title="Капремонт">
        <Overhaul overhaul={house.overhaul} />
      </Section>

      <Section title="Документы">
        <Documents house={house} />
      </Section>

      <Flex align="center" gap={12} className={styles.Note}>
        <Icon src={infoIcon} size={20} className={styles.NoteIcon} />
        <Typography.Text variant="description" color="secondary">
          Документы и реквизиты - модельные данные для демонстрации
        </Typography.Text>
      </Flex>
    </Panel>
  );
};

export const Component = HouseCardPage;
