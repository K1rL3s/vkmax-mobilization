import {
  Button,
  CellSimple,
  Flex,
  IconButton,
  Tappable,
  Typography,
} from "@maxhub/max-ui";
import { Link, useNavigate } from "react-router-dom";

import { useHouseCard } from "@/shared/model/house";
import { useSession } from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";
import { Card } from "@/shared/ui/card";
import {
  alertIcon,
  buildingIcon,
  chevronSmallIcon,
  homeIcon,
  Icon,
  megaphoneIcon,
  meterIcon,
  phoneIcon,
  pollIcon,
  wrenchIcon,
} from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import { DemandCard } from "./demand-card";
import { HOME_MOCK, type NewsKind } from "./home.mock";

import styles from "./home.module.css";

const NEWS_ICON: Record<NewsKind, { src: string; className: string }> = {
  alert: { src: alertIcon, className: styles.NewsIconAlert },
  announcement: { src: megaphoneIcon, className: styles.NewsIconAnnouncement },
};

const Chevron = () => (
  <Icon src={chevronSmallIcon} size={12} className={styles.Chevron} />
);

const HomePage = () => {
  const navigate = useNavigate();
  const { activeRequest, meters, poll, news } = HOME_MOCK;
  const { currentResidency: residency } = useSession();

  const card = useHouseCard(residency?.house_id);

  if (card.isPending) {
    return <LoadingState fill title="Загружаем ваш дом" />;
  }

  if (card.isError) {
    return <ErrorState fill onRetry={() => void card.refetch()} />;
  }

  const house = card.data;
  const connected = house.is_connected;

  return (
    <div className={styles.Page}>
      <Flex asChild align="center" gap={12}>
        <Tappable
          className={styles.HouseCard}
          onClick={() => navigate(Routes.PROFILE)}
        >
          <IconTile icon={homeIcon} tone="card" size="large" />
          <Flex
            className={styles.Grow}
            align="stretch"
            direction="column"
            gapY={2}
          >
            <Typography.Text
              variant="title"
              color="primary"
              className={styles.Ellipsis}
            >
              {house.address}
              {residency?.flat_number && `, кв. ${residency.flat_number}`}
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {house.city}
              {residency?.verified && " · квартира подтверждена"}
            </Typography.Text>
          </Flex>
          <Chevron />
        </Tappable>
      </Flex>

      {house.org && (
        <Card>
          <Flex align="center" gap={12}>
            <IconTile icon={buildingIcon} tone="neutral" />
            <Flex
              className={styles.Grow}
              align="stretch"
              direction="column"
              gapY={2}
            >
              <Typography.Text
                variant="body-strong"
                color="primary"
                className={styles.Ellipsis}
              >
                {house.org.name}
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                {house.org.reception_note ?? "Управляющая компания дома"}
              </Typography.Text>
            </Flex>
            <IconButton
              asChild
              variant="secondary"
              size="small"
              aria-label="Позвонить в УК"
            >
              <a href={`tel:${house.org.phone}`}>
                <Icon src={phoneIcon} className={styles.PhoneIcon} />
              </a>
            </IconButton>
          </Flex>

          {connected && (
            <Button asChild size="medium" stretched>
              <Link to={Routes.REQUESTS}>Подать заявку</Link>
            </Button>
          )}
        </Card>
      )}

      {!connected && (
        <DemandCard
          houseId={house.id}
          demandSent={house.demand_sent}
          demandCount={house.demand_count}
          onSent={() => void card.refetch()}
        />
      )}

      {connected && (
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Актуальное</h2>
            </Typography.Text>

            <Flex asChild align="center" gap={12}>
              <Tappable
                className={styles.CardLink}
                onClick={() => navigate(Routes.REQUESTS)}
              >
                <IconTile icon={wrenchIcon} tone="themed" />
                <Flex
                  className={styles.Grow}
                  align="stretch"
                  direction="column"
                  gapY={4}
                >
                  <Flex align="center" gap={12}>
                    <Typography.Text
                      variant="description"
                      color="secondary"
                      className={styles.Grow}
                    >
                      Заявка №{activeRequest.number}
                    </Typography.Text>
                    <Typography.Text
                      variant="label-strong"
                      className={styles.StatusPill}
                    >
                      {activeRequest.status}
                    </Typography.Text>
                  </Flex>
                  <Typography.Text
                    variant="body-strong"
                    color="primary"
                    className={styles.Ellipsis}
                  >
                    {activeRequest.title}
                  </Typography.Text>
                  <div className={styles.Deadline}>
                    <div className={styles.ProgressTrack}>
                      <div
                        className={styles.ProgressFill}
                        style={{
                          width: `${activeRequest.deadlineProgress * 100}%`,
                        }}
                      />
                    </div>
                    <Typography.Text variant="description" color="secondary">
                      {activeRequest.deadlineLeft}
                    </Typography.Text>
                  </div>
                </Flex>
                <Chevron />
              </Tappable>
            </Flex>

            <Flex asChild align="center" gap={12}>
              <Card>
                <IconTile icon={meterIcon} tone="positive" />
                <Flex
                  className={styles.Grow}
                  align="stretch"
                  direction="column"
                  gapY={2}
                >
                  <Typography.Text variant="body-strong" color="primary">
                    Передать показания
                  </Typography.Text>
                  <Typography.Text variant="description" color="secondary">
                    {meters.windowLeft}
                  </Typography.Text>
                </Flex>
                <Button asChild size="small">
                  <Link to={Routes.PROFILE}>Передать</Link>
                </Button>
              </Card>
            </Flex>

            <Flex asChild align="center" gap={12}>
              <Card>
                <IconTile icon={pollIcon} tone="promo" />
                <Flex
                  className={styles.Grow}
                  align="stretch"
                  direction="column"
                  gapY={2}
                >
                  <Typography.Text variant="body-strong" color="primary">
                    {poll.title}
                  </Typography.Text>
                  <Typography.Text variant="description" color="secondary">
                    {poll.deadline}
                  </Typography.Text>
                </Flex>
                <Button asChild size="small" variant="secondary">
                  <Link to={Routes.MEETINGS}>Голосовать</Link>
                </Button>
              </Card>
            </Flex>
          </section>
        </Flex>
      )}

      {connected && (
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Flex align="center" gap={12}>
              <Typography.Text
                asChild
                variant="title"
                color="primary"
                className={styles.Grow}
              >
                <h2>Новости дома</h2>
              </Typography.Text>
              {/* TODO: экран со всеми новостями дома пока не спроектирован */}
              <Typography.Text
                variant="detail-strong"
                className={styles.SectionAction}
              >
                Все
              </Typography.Text>
            </Flex>

            <div className={styles.NewsPanel}>
              {news.map((item) => (
                <CellSimple
                  key={item.id}
                  before={
                    <Icon
                      src={NEWS_ICON[item.kind].src}
                      className={NEWS_ICON[item.kind].className}
                    />
                  }
                  title={item.title}
                  subtitle={item.subtitle}
                  showChevron
                />
              ))}
            </div>
          </section>
        </Flex>
      )}
    </div>
  );
};

export const Component = HomePage;
