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
import { residencyState } from "@/features/flat-confirmation";
import { HouseSummary, OutagesPanel, useHouseCard } from "@/features/house";
import { useHouseProblems } from "@/features/house-problems";
import { useNextPoll } from "@/features/meetings";
import {
  announcementWhen,
  useLatestAnnouncements,
} from "@/features/announcements";
import { formatPeriod, useOpenReadingPeriod } from "@/features/meters";
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
  Icon,
  megaphoneIcon,
  meterIcon,
  phoneIcon,
  pollIcon,
  usersIcon,
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

const AnnouncementsSection = () => {
  const navigate = useNavigate();
  const announcements = useLatestAnnouncements();
  const items = announcements.data?.items ?? [];

  const content = () => {
    if (announcements.isPending) {
      return <LoadingState />;
    }

    if (announcements.isError) {
      return (
        <CellSimple
          before={
            <Icon src={alertIcon} className={styles.AnnouncementIconAlert} />
          }
          title="Объявления не загрузились"
          after={
            <Button
              size="small"
              variant="secondary"
              onClick={() => void announcements.refetch()}
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
          before={
            <Icon
              src={megaphoneIcon}
              className={styles.AnnouncementIconMuted}
            />
          }
          title="Объявлений пока нет"
          subtitle="Здесь появятся объявления управляющей компании"
        />
      );
    }

    return items.map((item) => (
      <Tappable
        key={item.id}
        className={styles.AnnouncementRow}
        onClick={() => void navigate(Routes.ANNOUNCEMENTS)}
      >
        <IconTile
          icon={item.urgent ? alertIcon : megaphoneIcon}
          tone={item.urgent ? "negative" : "themed"}
        />

        <Flex
          className={styles.Grow}
          align="stretch"
          direction="column"
          gapY={4}
        >
          <Typography.Text
            className={styles.Ellipsis}
            variant="description"
            color="tertiary"
          >
            {[item.org_name, announcementWhen(item.created_at)]
              .filter(Boolean)
              .join(" · ")}
          </Typography.Text>

          <Typography.Text
            className={styles.TwoLines}
            variant="body-strong"
            color="primary"
          >
            {item.text}
          </Typography.Text>
        </Flex>

        <Chevron />
      </Tappable>
    ));
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
            <h2>Объявления</h2>
          </Typography.Text>
          {items.length > 0 && (
            <Typography.Text
              asChild
              variant="detail-strong"
              className={styles.SectionAction}
            >
              <Link to={Routes.ANNOUNCEMENTS}>Все</Link>
            </Typography.Text>
          )}
        </Flex>

        <div className={styles.AnnouncementsPanel}>{content()}</div>
      </section>
    </Flex>
  );
};

const HomePage = () => {
  const navigate = useNavigate();
  const poll = useNextPoll();
  const { currentResidency: residency } = useSession();
  const request = useActiveRequest();
  const openPeriod = useOpenReadingPeriod();
  const problems = useHouseProblems().data;

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
      <HouseSummary
        title={house.address}
        flat={residency?.flat_number}
        state={residency ? residencyState(residency) : "not-connected"}
        onClick={() => void navigate(Routes.FLAT)}
      />

      <OutagesPanel outages={house.outages} />

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
          house={house}
          flat={residency?.flat_number}
          onSent={() => void card.refetch()}
        />
      )}

      {connected && (request || openPeriod || poll || problems) && (
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Актуальное</h2>
            </Typography.Text>

            {request && <ActiveRequestCard request={request} />}

            {openPeriod && (
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
                      Окно открыто · {formatPeriod(openPeriod.period)}
                    </Typography.Text>
                  </Flex>
                  <Button asChild size="small">
                    <Link to={Routes.METERS}>Передать</Link>
                  </Button>
                </Card>
              </Flex>
            )}

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

            {problems && (
              <Flex asChild align="center" gap={12}>
                <Card>
                  <IconTile icon={usersIcon} tone="themed" />
                  <Flex
                    className={styles.Grow}
                    align="stretch"
                    direction="column"
                    gapY={2}
                  >
                    <Typography.Text variant="body-strong" color="primary">
                      Проблемы дома
                    </Typography.Text>
                    <Typography.Text variant="description" color="secondary">
                      Открыто: {problems.open.length} · что сообщили соседи
                    </Typography.Text>
                  </Flex>
                  <Button asChild size="small" variant="secondary">
                    <Link to={Routes.HOUSE_PROBLEMS}>Смотреть</Link>
                  </Button>
                </Card>
              </Flex>
            )}
          </section>
        </Flex>
      )}

      {connected && <AnnouncementsSection />}
    </Panel>
  );
};

export const Component = HomePage;
