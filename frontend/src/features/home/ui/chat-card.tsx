import { Button, Flex, Typography } from "@maxhub/max-ui";

import type { HouseCard } from "@/features/house";
import { errorMessage } from "@/shared/api/errors";
import { Card } from "@/shared/ui/card";
import { FieldError } from "@/shared/ui/field-error";
import { usersIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import { useChatJoin } from "../model/use-chat-join";

import styles from "./chat-card.module.css";

type ChatCardProps = {
  house: HouseCard;
  updatedAt: number;
};

export const ChatCard = ({ house, updatedAt }: ChatCardProps) => {
  const chat = useChatJoin(house, updatedAt);

  if (!chat) {
    return null;
  }

  const waiting = chat.kind === "join" && chat.waiting;

  return (
    <Flex asChild align="stretch" direction="column" gap={12}>
      <Card>
        <Flex align="center" gap={12}>
          <IconTile icon={usersIcon} tone="themed" />
          <Flex
            className={styles.Grow}
            align="stretch"
            direction="column"
            gapY={2}
          >
            <Typography.Text variant="body-strong" color="primary">
              Чат дома
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {waiting ? "Бот добавит вас и напишет в личку" : chat.title}
            </Typography.Text>
          </Flex>
          {chat.kind === "open" ? (
            <Button size="small" variant="secondary" onClick={chat.open}>
              Открыть чат
            </Button>
          ) : (
            <Button
              size="small"
              variant="secondary"
              disabled={waiting}
              loading={chat.pending}
              onClick={chat.request}
            >
              Вступить
            </Button>
          )}
        </Flex>

        {chat.kind === "join" && chat.error && (
          <FieldError
            message={errorMessage(
              chat.error,
              "Не получилось отправить. Попробуйте ещё раз",
            )}
          />
        )}
      </Card>
    </Flex>
  );
};
