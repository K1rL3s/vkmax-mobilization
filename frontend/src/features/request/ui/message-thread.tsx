import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { formatTime } from "@/shared/lib/format";
import {
  buildingIcon,
  Icon,
  lockIcon,
  userIcon,
  wrenchIcon,
} from "@/shared/ui/icon";

import { groupMessagesByDay } from "../domain/messages";
import type { RequestMessage } from "../domain/types";

import styles from "./message-thread.module.css";

const AUTHOR_ROLE: Record<string, { icon: string; tone: string }> = {
  executor: { icon: wrenchIcon, tone: styles.executor },
  staff: { icon: buildingIcon, tone: styles.staff },
};

export const MessageThread = ({
  messages,
  ownRole,
}: {
  messages: RequestMessage[];
  ownRole?: string;
}) => {
  if (messages.length === 0) return null;

  return (
    <div className={styles.Thread}>
      {groupMessagesByDay(messages).map((group) => (
        <div key={group.day} className={styles.Day}>
          {group.label && (
            <Typography.Text
              className={styles.DayLabel}
              variant="description"
              color="secondary"
            >
              {group.label}
            </Typography.Text>
          )}
          {group.messages.map((message, index) => {
            const role = AUTHOR_ROLE[message.author_role] ?? {
              icon: userIcon,
              tone: styles.resident,
            };

            return (
              <div
                key={`${message.created_at}-${index}`}
                className={styles.Message}
              >
                <Flex align="center" gap={8}>
                  <span className={cn(styles.Avatar, role.tone)}>
                    <Icon src={role.icon} size={16} />
                  </span>
                  <Typography.Text
                    className={styles.Author}
                    variant="body-strong"
                    color="primary"
                  >
                    {message.author_role === ownRole
                      ? "Вы"
                      : message.author_name}
                  </Typography.Text>
                  {message.is_internal && (
                    <Typography.Text
                      className={styles.Internal}
                      variant="label-strong"
                    >
                      <Icon src={lockIcon} size={14} />
                      Только УК
                    </Typography.Text>
                  )}
                  <Typography.Text
                    className={styles.Time}
                    variant="description"
                    color="tertiary"
                  >
                    {formatTime(message.created_at)}
                  </Typography.Text>
                </Flex>
                <Typography.Text
                  className={styles.Text}
                  variant="body"
                  color="primary"
                >
                  {message.text}
                </Typography.Text>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};
