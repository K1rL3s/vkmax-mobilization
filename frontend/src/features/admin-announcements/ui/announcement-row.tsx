import { Flex, Typography } from "@maxhub/max-ui";

import { announcementWhen } from "@/features/announcements";
import { Card } from "@/shared/ui/card";
import { alertIcon, megaphoneIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import {
  addressees,
  channelsLabel,
  deliveryLabel,
  undeliveredReason,
} from "../domain/labels";
import type { Announcement, OrgHouse } from "../model/use-announcements";

import styles from "./announcement-row.module.css";

type AnnouncementRowProps = {
  announcement: Announcement;
  houses: OrgHouse[];
};

export const AnnouncementRow = ({
  announcement,
  houses,
}: AnnouncementRowProps) => (
  <Card>
    <Flex align="center" gap={12}>
      <IconTile
        icon={announcement.urgent ? alertIcon : megaphoneIcon}
        tone={announcement.urgent ? "negative" : "themed"}
      />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          {announcement.urgent ? "Срочное объявление" : "Объявление"}
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {announcementWhen(announcement.created_at)}
        </Typography.Text>
      </Flex>
    </Flex>

    <Typography.Text className={styles.Text} variant="body" color="primary">
      {announcement.text}
    </Typography.Text>

    <Flex align="stretch" direction="column" gapY={2}>
      <Typography.Text
        className={styles.Ellipsis}
        variant="description"
        color="secondary"
      >
        {addressees(announcement.house_ids, houses)}
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
  </Card>
);
