import {
  Button,
  CellSimple,
  Flex,
  IconButton,
  Panel,
  Tappable,
  Typography,
} from "@maxhub/max-ui";
import { generatePath, Link, useNavigate } from "react-router-dom";

import { EmergencyCard } from "@/features/emergency";
import { confirmationCaption } from "@/features/flat-confirmation";
import { useHouseCard } from "@/features/house";
import { useNextPoll } from "@/features/meetings";
import { newsWhen, useLatestNews } from "@/features/news";
import { useReadingsHint } from "@/features/meters";
import {
  CATEGORY_ICON,
  deadlineLeft,
  deadlineProgress,
  isOnReview,
  type RequestListItem,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/features/request";
import { cn } from "@/shared/lib/css";
import { formatDay } from "@/shared/lib/format";
import { useSession } from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";
import { Card } from "@/shared/ui/card";
import { Chevron } from "@/shared/ui/chevron";
import {
  alertIcon,
  buildingIcon,
  homeIcon,
  Icon,
  megaphoneIcon,
  meterIcon,
  phoneIcon,
  pollIcon,
} from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { DemandCard } from "./demand-card";
import { useActiveRequest } from "./use-active-request";

import styles from "./home.module.css";

const ActiveRequestCard = ({ request }: { request: RequestListItem }) => {
  const navigate = useNavigate();
  const tone = STATUS_TONE[request.status];
  const onReview = isOnReview(request.status);
  const deadline = onReview ? null : deadlineLeft(request.deadline_at);
  const progress = onReview
    ? null
    : deadlineProgress(request.created_at, request.deadline_at);
  const hint = onReview ? "Проверьте работу" : deadline?.text;

  return (
    <Flex asChild align="center" gap={12}>
      <Tappable
        className={styles.CardLink}
        onClick={() =>
          void navigate(
            generatePath(Routes.REQUEST, { requestId: String(request.id) }),
          )
        }
      >
        <IconTile icon={CATEGORY_ICON[request.category]} tone={tone} />
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
              Заявка №{request.id}
            </Typography.Text>
            <StatusPill tone={tone}>{STATUS_LABEL[request.status]}</StatusPill>
          </Flex>
          <Typography.Text
            variant="body-strong"
            color="primary"
            className={styles.Ellipsis}
          >
            {request.description}
          </Typography.Text>
          {hint && (
            <div className={styles.Deadline}>
              {progress !== null && (
                <div className={styles.ProgressTrack}>
                  <div
                    className={cn(
                      styles.ProgressFill,
                      deadline?.overdue && styles.overdue,
                    )}
                    style={{ width: `${progress * 100}%` }}
                  />
                </div>
              )}
              <Typography.Text
                variant="description"
                className={cn(
                  styles.Hint,
                  onReview && styles.action,
                  deadline?.overdue && styles.overdue,
                )}
              >
                {hint}
              </Typography.Text>
            </div>
          )}
        </Flex>
        <Chevron />
      </Tappable>
    </Flex>
  );
};

const NewsSection = () => {
  const news = useLatestNews();
  const items = news.data?.items ?? [];

  const content = () => {
    if (news.isPending) {
      return <LoadingState />;
    }

    if (news.isError) {
      return (
        <CellSimple
          before={<Icon src={alertIcon} className={styles.NewsIconAlert} />}
          title="Новости не загрузились"
          after={
            <Button
              size="small"
              variant="secondary"
              onClick={() => void news.refetch()}
            >
              Повторить
            </Button>
          }
        />
      );
    }

    if (items.length === 0) {
      return (
        <CellSimple
          before={<Icon src={megaphoneIcon} className={styles.NewsIconMuted} />}
          title="Объявлений пока нет"
          subtitle="Здесь появятся новости от управляющей компании"
        />
      );
    }

    return items.map((item) => {
      const when = newsWhen(item.created_at);

      return (
        <CellSimple
          key={item.id}
          asChild
          before={
            <Icon
              src={item.urgent ? alertIcon : megaphoneIcon}
              className={
                item.urgent ? styles.NewsIconAlert : styles.NewsIconAnnouncement
              }
            />
          }
          title={item.text}
          subtitle={item.urgent ? `Срочное · ${when}` : when}
          innerClassNames={{ title: styles.TwoLines }}
          showChevron
        >
          <Link to={Routes.NEWS} />
        </CellSimple>
      );
    });
  };

  return (
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
          {items.length > 0 && (
            <Typography.Text
              asChild
              variant="detail-strong"
              className={styles.SectionAction}
            >
              <Link to={Routes.NEWS}>Все</Link>
            </Typography.Text>
          )}
        </Flex>

        <div className={styles.NewsPanel}>{content()}</div>
      </section>
    </Flex>
  );
};

const HomePage = () => {
  const navigate = useNavigate();
  const poll = useNextPoll();
  const { currentResidency: residency } = useSession();
  const request = useActiveRequest();
  const readingsHint = useReadingsHint();

  const card = useHouseCard(residency?.house_id);

  if (card.isPending) {
    return <LoadingState fill title="Загружаем ваш дом" />;
  }

  if (card.isError) {
    return (
      <ErrorState error={card.error} fill onRetry={() => void card.refetch()} />
    );
  }

  const house = card.data;
  const connected = house.is_connected;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex asChild align="center" gap={12}>
        <Tappable
          className={styles.HouseCard}
          onClick={() => void navigate(Routes.FLAT)}
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
              {residency && ` · ${confirmationCaption(residency)}`}
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
              <Link to={Routes.REQUEST_NEW}>Подать заявку</Link>
            </Button>
          )}
        </Card>
      )}

      {!connected && <EmergencyCard org={house.org} />}

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

            {request && <ActiveRequestCard request={request} />}

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
                  {readingsHint && (
                    <Typography.Text variant="description" color="secondary">
                      {readingsHint}
                    </Typography.Text>
                  )}
                </Flex>
                <Button asChild size="small">
                  <Link to={Routes.METERS}>Передать</Link>
                </Button>
              </Card>
            </Flex>

            {poll && (
              <Flex asChild align="center" gap={12}>
                <Card>
                  <IconTile icon={pollIcon} tone="promo" />
                  <Flex
                    className={styles.Grow}
                    align="stretch"
                    direction="column"
                    gapY={2}
                  >
                    <Typography.Text
                      className={styles.TwoLines}
                      variant="body-strong"
                      color="primary"
                    >
                      {poll.title}
                    </Typography.Text>
                    <Typography.Text variant="description" color="secondary">
                      до {formatDay(poll.ends_at)}
                    </Typography.Text>
                  </Flex>
                  <Button asChild size="small" variant="secondary">
                    <Link
                      to={generatePath(Routes.MEETING, {
                        pollId: String(poll.id),
                      })}
                    >
                      Голосовать
                    </Link>
                  </Button>
                </Card>
              </Flex>
            )}
          </section>
        </Flex>
      )}

      {connected && <NewsSection />}
    </Panel>
  );
};

export const Component = HomePage;
