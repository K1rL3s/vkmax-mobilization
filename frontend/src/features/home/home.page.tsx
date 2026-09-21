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

import { confirmationCaption } from "@/features/flat-confirmation";
import { useHouseCard } from "@/features/house";
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

import { DemandCard } from "./demand-card";
import { HOME_MOCK, type NewsKind } from "./home.mock";
import { useActiveRequest } from "./use-active-request";

import styles from "./home.module.css";

const NEWS_ICON: Record<NewsKind, { src: string; className: string }> = {
  alert: { src: alertIcon, className: styles.NewsIconAlert },
  announcement: { src: megaphoneIcon, className: styles.NewsIconAnnouncement },
};

const ActiveRequestCard = ({ request }: { request: RequestListItem }) => {
  const navigate = useNavigate();
  const tone = STATUS_TONE[request.status];
  // на приёмке нормативный срок уже не идёт: работы сделаны, ход за жителем
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
            <Typography.Text
              variant="label-strong"
              className={cn(styles.StatusPill, styles[tone])}
            >
              {STATUS_LABEL[request.status]}
            </Typography.Text>
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

const HomePage = () => {
  const navigate = useNavigate();
  const { poll, news } = HOME_MOCK;
  const { currentResidency: residency } = useSession();
  const request = useActiveRequest();
  const readingsHint = useReadingsHint();

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
    </Panel>
  );
};

export const Component = HomePage;
