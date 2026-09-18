import type { ReactNode } from "react";
import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { IconTile, type IconTileTone } from "@/shared/ui/icon-tile";

import styles from "./state-message.module.css";

type StateMessageProps = {
  title: string;
  description?: string;
  icon?: string;
  tone?: IconTileTone;
  action?: ReactNode;
  fill?: boolean;
  className?: string;
};

export const StateMessage = ({
  title,
  description,
  icon,
  tone = "secondary",
  action,
  fill = false,
  className,
}: StateMessageProps) => {
  return (
    <Flex
      className={cn(styles.Message, fill && styles.fill, className)}
      direction="column"
      align="center"
      justify="center"
      gap={12}
    >
      {icon && <IconTile icon={icon} tone={tone} size="large" />}

      <Flex direction="column" align="center" gapY={4}>
        <Typography.Text variant="body-strong" color="primary">
          {title}
        </Typography.Text>

        {description && (
          <Typography.Text
            className={styles.Description}
            variant="description"
            color="secondary"
          >
            {description}
          </Typography.Text>
        )}
      </Flex>

      {action}
    </Flex>
  );
};
