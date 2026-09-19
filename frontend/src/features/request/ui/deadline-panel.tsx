import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";

import { deadlineLeft, deadlineProgress, plural } from "../domain/format";
import { formatDayTime } from "../domain/format";
import type { RequestCard } from "../domain/types";

import styles from "./deadline-panel.module.css";

export const DeadlinePanel = ({ request }: { request: RequestCard }) => {
  const left = deadlineLeft(request.deadline_at);
  const progress = deadlineProgress(request.created_at, request.deadline_at);
  const hours = request.normative_hours;

  return (
    <div className={styles.Panel}>
      <Flex align="center" gap={8}>
        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          Нормативный срок
        </Typography.Text>
        {left && (
          <Typography.Text
            className={cn(styles.Left, left.overdue && styles.overdue)}
            variant="description"
          >
            {left.text}
          </Typography.Text>
        )}
      </Flex>

      {progress !== null && (
        <div className={styles.Track}>
          <div
            className={cn(styles.Fill, left?.overdue && styles.overdue)}
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      )}

      <Typography.Text variant="description" color="secondary">
        {request.deadline_at && `До ${formatDayTime(request.deadline_at)} · `}
        норматив {hours} {plural(hours, ["час", "часа", "часов"])}
      </Typography.Text>
    </div>
  );
};
