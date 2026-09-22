import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";

import { deadlineLabel, votedLine } from "@/features/meetings";
import type { components } from "@/shared/api/schema/generated";
import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { StatusPill } from "@/shared/ui/status-pill";

import styles from "./admin-poll-row.module.css";

export type AdminPoll = components["schemas"]["AdminPollListItem"];

export const AdminPollRow = ({ poll }: { poll: AdminPoll }) => {
  const navigate = useNavigate();
  const isActive = poll.status === "active";

  return (
    <Tappable
      className={styles.Row}
      onClick={() =>
        void navigate(
          generatePath(Routes.ADMIN_POLL, { pollId: String(poll.id) }),
        )
      }
    >
      <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
        <Flex align="flex-start" gap={8}>
          <Typography.Text
            className={cn(styles.Grow, styles.Title)}
            variant="body-strong"
            color="primary"
          >
            {poll.title}
          </Typography.Text>

          <StatusPill tone={isActive ? "themed" : "neutral"}>
            {isActive ? "Идёт" : "Завершён"}
          </StatusPill>
        </Flex>

        <Typography.Text
          className={styles.Ellipsis}
          variant="description"
          color="secondary"
        >
          {poll.address}
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {deadlineLabel(poll)}
        </Typography.Text>

        {/* свой голос сотрудника в списке УК ни при чём: строка про квартиры
            дома, как у жителя, который ещё не голосовал */}
        <Typography.Text variant="description" color="secondary">
          {votedLine({ ...poll, voted: false })}
        </Typography.Text>
      </Flex>

      <Chevron />
    </Tappable>
  );
};
