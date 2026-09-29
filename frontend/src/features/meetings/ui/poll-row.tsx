import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { pollIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import {
  authorCaption,
  deadlineLabel,
  isInitiative,
  votedLine,
  type PollListItem,
} from "../domain/poll";

import styles from "./poll-row.module.css";

export const PollRow = ({ poll }: { poll: PollListItem }) => {
  const navigate = useNavigate();
  const isActive = poll.status === "active";

  return (
    <Tappable
      className={styles.Row}
      onClick={() =>
        void navigate(generatePath(Routes.MEETING, { pollId: String(poll.id) }))
      }
    >
      <IconTile icon={pollIcon} tone={isActive ? "themed" : "neutral"} />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
        <Typography.Text variant="description" color="secondary">
          {isInitiative(poll) && `${authorCaption(poll.created_by_role)} · `}
          {deadlineLabel(poll)}
        </Typography.Text>

        <Typography.Text
          className={styles.Title}
          variant="body-strong"
          color="primary"
        >
          {poll.title}
        </Typography.Text>

        <Typography.Text
          className={poll.voted ? styles.Voted : undefined}
          variant="description"
          color={poll.voted ? undefined : "secondary"}
        >
          {votedLine(poll)}
        </Typography.Text>
      </Flex>

      <Chevron />
    </Tappable>
  );
};
