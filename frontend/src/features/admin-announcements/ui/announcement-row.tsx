import { Button, Flex, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import {
  announcementWhen,
  worksState,
  WorksDetails,
} from "@/features/announcements";
import { Routes } from "@/shared/model/routes";
import { Card } from "@/shared/ui/card";
import { alertIcon, megaphoneIcon, wrenchIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import {
  addressees,
  channelsLabel,
  deliveryLabel,
  scopeLabel,
  undeliveredReason,
} from "../domain/labels";
import type { Announcement, OrgHouse } from "../model/use-announcements";

import styles from "./announcement-row.module.css";

type AnnouncementRowProps = {
  announcement: Announcement;
  houses: OrgHouse[];
  withRegister: boolean;
  onFinish: () => void;
};

export const AnnouncementRow = ({
  announcement,
  houses,
  withRegister,
  onFinish,
}: AnnouncementRowProps) => (
  <Card>
    <Flex align="center" gap={12}>
      <IconTile
        icon={
          announcement.urgent
            ? alertIcon
            : announcement.works
              ? wrenchIcon
              : megaphoneIcon
        }
        tone={announcement.urgent ? "negative" : "themed"}
      />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          {announcement.urgent
            ? "Срочное объявление"
            : announcement.works
              ? "Плановые работы"
              : "Объявление"}
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {announcementWhen(announcement.created_at)}
        </Typography.Text>
      </Flex>
    </Flex>

    <Typography.Text className={styles.Text} variant="body" color="primary">
      {announcement.text}
    </Typography.Text>

    <WorksDetails announcement={announcement} />

    <Flex align="stretch" direction="column" gapY={2}>
      <Typography.Text
        className={styles.Ellipsis}
        variant="description"
        color="secondary"
      >
        {[addressees(announcement.house_ids, houses), scopeLabel(announcement)]
          .filter(Boolean)
          .join(" · ")}
      </Typography.Text>

      <Typography.Text variant="description" color="secondary">
        {channelsLabel(announcement.channels)} · {deliveryLabel(announcement)}
      </Typography.Text>

      {announcement.delivered_count !== null &&
        announcement.delivered_count < announcement.recipients_count && (
          <Typography.Text variant="description" color="secondary">
            Остальным не дошло: {undeliveredReason(announcement)}
          </Typography.Text>
        )}
    </Flex>

    {withRegister && announcement.channels.includes("direct") && (
      <Button asChild size="medium" variant="secondary">
        <Link
          to={generatePath(Routes.ADMIN_ANNOUNCEMENT_REGISTER, {
            announcementId: String(announcement.id),
          })}
        >
          Реестр уведомлений
        </Link>
      </Button>
    )}

    {announcement.works && worksState(announcement.works) === "going" && (
      <Button size="medium" variant="secondary" onClick={onFinish}>
        Завершить досрочно
      </Button>
    )}
  </Card>
);
