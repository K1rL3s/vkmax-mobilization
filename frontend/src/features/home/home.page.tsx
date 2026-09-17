import {
  Button,
  CellSimple,
  IconButton,
  Tappable,
  Typography,
} from "@maxhub/max-ui";
import { Link, useNavigate } from "react-router-dom";

import { cn } from "@/shared/lib/css";
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
  const { house, company, activeRequest, meters, poll, news } = HOME_MOCK;

  return (
    <div className={styles.Page}>
      <Tappable
        className={cn(styles.Row, styles.HouseCard)}
        onClick={() => navigate(Routes.PROFILE)}
      >
        <IconTile icon={homeIcon} tone="card" size="large" />
        <div className={styles.Text}>
          <Typography.Text
            variant="title"
            color="primary"
            className={styles.Ellipsis}
          >
            {house.address}
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            {house.city}
            {house.isVerified && " · квартира подтверждена"}
          </Typography.Text>
        </div>
        <Chevron />
      </Tappable>

      <Card>
        <div className={styles.Row}>
          <IconTile icon={buildingIcon} tone="neutral" />
          <div className={styles.Text}>
            <Typography.Text
              variant="body-strong"
              color="primary"
              className={styles.Ellipsis}
            >
              {company.name}
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {company.schedule}
            </Typography.Text>
          </div>
          <IconButton
            asChild
            variant="secondary"
            size="small"
            aria-label="Позвонить в УК"
          >
            <a href={`tel:${company.phone}`}>
              <Icon src={phoneIcon} className={styles.PhoneIcon} />
            </a>
          </IconButton>
        </div>

        <Button asChild size="medium" stretched>
          <Link to={Routes.REQUESTS}>Подать заявку</Link>
        </Button>
      </Card>

      <section className={styles.Section}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Актуальное</h2>
        </Typography.Text>

        <Tappable
          className={cn(styles.Row, styles.CardLink)}
          onClick={() => navigate(Routes.REQUESTS)}
        >
          <IconTile icon={wrenchIcon} tone="themed" />
          <div className={cn(styles.Text, styles.RequestText)}>
            <div className={styles.Row}>
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
            </div>
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
          </div>
          <Chevron />
        </Tappable>

        <Card className={styles.Row}>
          <IconTile icon={meterIcon} tone="positive" />
          <div className={styles.Text}>
            <Typography.Text variant="body-strong" color="primary">
              Передать показания
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {meters.windowLeft}
            </Typography.Text>
          </div>
          <Button asChild size="small">
            <Link to={Routes.PROFILE}>Передать</Link>
          </Button>
        </Card>

        <Card className={styles.Row}>
          <IconTile icon={pollIcon} tone="promo" />
          <div className={styles.Text}>
            <Typography.Text variant="body-strong" color="primary">
              {poll.title}
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {poll.deadline}
            </Typography.Text>
          </div>
          <Button asChild size="small" variant="secondary">
            <Link to={Routes.MEETINGS}>Голосовать</Link>
          </Button>
        </Card>
      </section>

      <section className={styles.Section}>
        <div className={styles.Row}>
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
        </div>

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
    </div>
  );
};

export const Component = HomePage;
