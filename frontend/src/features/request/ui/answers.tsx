import { Flex, Typography } from "@maxhub/max-ui";

import { formatDayTime } from "@/shared/lib/format";
import type { RequestCard } from "../domain/types";

import styles from "./answers.module.css";

export const Answers = ({
  messages,
}: {
  messages: RequestCard["messages"];
}) => {
  return (
    <div className={styles.Answers}>
      {messages.map((message) => (
        <div key={message.created_at} className={styles.Message}>
          <Flex align="center" gap={8}>
            <Typography.Text
              className={styles.Grow}
              variant="description"
              color="secondary"
            >
              {message.author_name}
            </Typography.Text>
            <Typography.Text variant="description" color="tertiary">
              {formatDayTime(message.created_at)}
            </Typography.Text>
          </Flex>
          <Typography.Text variant="body" color="primary">
            {message.text}
          </Typography.Text>
        </div>
      ))}
    </div>
  );
};
