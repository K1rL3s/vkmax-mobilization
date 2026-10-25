import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { formatTime } from "@/shared/lib/format";
import {
  alertIcon,
  buildingIcon,
  checkIcon,
  clockIcon,
  Icon,
  infoIcon,
  lockIcon,
  userIcon,
  wrenchIcon,
} from "@/shared/ui/icon";

import { deliveryMark } from "../domain/delivery";
import { groupMessagesByDay } from "../domain/messages";
import type { RequestMessage } from "../domain/types";

import styles from "./message-thread.module.css";

const AUTHOR_ROLE: Record<string, { icon: string; tone: string }> = {
  executor: { icon: wrenchIcon, tone: styles.executor },
  staff: { icon: buildingIcon, tone: styles.staff },
};

const DELIVERY: Record<
  NonNullable<ReturnType<typeof deliveryMark>>,
  { icon: string; tone: string; text: string }
> = {
  read: { icon: checkIcon, tone: styles.read, text: "Прочитано" },
  pending: { icon: clockIcon, tone: styles.sent, text: "Отправляем в MAX" },
  unknown: { icon: infoIcon, tone: styles.sent, text: "Нет данных о доставке" },
  delivered: { icon: checkIcon, tone: styles.sent, text: "Отправлено в MAX" },
  failed: { icon: alertIcon, tone: styles.failed, text: "Не доставлено в MAX" },
  muted: {
    icon: alertIcon,
    tone: styles.failed,
    text: "Не доставлено: житель отключил уведомления",
  },
  bot_stopped: {
    icon: alertIcon,
    tone: styles.failed,
    text: "Не доставлено: житель остановил бота",
  },
};

export const MessageThread = ({
  messages,
  ownRole,
  showDelivery = false,
}: {
  messages: RequestMessage[];
  ownRole?: string;
  showDelivery?: boolean;
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
            const mark = showDelivery ? deliveryMark(message) : null;
            const delivery = mark && DELIVERY[mark];

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
                {delivery && (
                  <Typography.Text
                    className={styles.Delivery}
                    variant="description"
                    color="secondary"
                  >
                    <Icon
                      className={delivery.tone}
                      src={delivery.icon}
                      size={14}
                    />
                    {delivery.text}
                  </Typography.Text>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};
