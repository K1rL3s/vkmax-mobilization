import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { Icon } from "@/shared/ui/icon";

import styles from "./notice.module.css";

type NoticeProps = {
  icon: string;
  tone: "info" | "alert";
  title: string;
  text: string;
};

export const Notice = ({ icon, tone, title, text }: NoticeProps) => {
  return (
    <Flex
      className={styles.Notice}
      direction="column"
      align="stretch"
      gapY={12}
    >
      <Typography.Text variant="body-strong" color="primary">
        {title}
      </Typography.Text>

      <Flex align="center" gap={12}>
        <Icon src={icon} className={cn(styles.Icon, styles[tone])} />

        <Typography.Text variant="description" color="secondary">
          {text}
        </Typography.Text>
      </Flex>
    </Flex>
  );
};
