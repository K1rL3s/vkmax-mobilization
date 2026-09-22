import { Button, Flex, Typography } from "@maxhub/max-ui";

import { Card } from "@/shared/ui/card";
import { alertIcon, checkIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import { recipientsCount } from "../domain/labels";
import type { SentOutcome } from "../model/use-announcements";

import styles from "./sent-notice.module.css";

type SentNoticeProps = {
  sent: SentOutcome;
  onClose: () => void;
};

export const SentNotice = ({ sent, onClose }: SentNoticeProps) => {
  const isLost = sent.recipients === 0;

  return (
    <Card role="status">
      <Flex align="center" gap={12}>
        <IconTile
          icon={isLost ? alertIcon : checkIcon}
          tone={isLost ? "negative" : "positive"}
        />

        <Flex
          className={styles.Grow}
          align="stretch"
          direction="column"
          gapY={2}
        >
          <Typography.Text variant="body-strong" color="primary">
            {isLost ? "Объявление никто не получил" : "Объявление отправлено"}
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            {isLost
              ? "Адресатов не нашлось"
              : `Получат ${recipientsCount(sent.recipients)}`}
          </Typography.Text>
        </Flex>
      </Flex>

      <Typography.Text variant="description" color="secondary">
        Чат дома - один адресат, в личных сообщениях адресат - каждый житель,
        подключивший бота.
      </Typography.Text>

      {sent.withoutChat.length > 0 && (
        <Typography.Text className={styles.Warning} variant="description">
          В чат не ушло - у этих домов он не привязан:{" "}
          {sent.withoutChat.join("; ")}. Привяжите чат в карточке дома или
          отправляйте этим домам в личные сообщения.
        </Typography.Text>
      )}

      <Button size="medium" variant="secondary" stretched onClick={onClose}>
        Понятно
      </Button>
    </Card>
  );
};
