import type { ReactNode } from "react";
import { Button, Flex, Spinner, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { alertIcon } from "@/shared/ui/icon";
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

export const EmptyState = (props: {
  title: string;
  description: string;
  icon?: string;
  action?: ReactNode;
  fill?: boolean;
}) => <StateMessage {...props} />;

export const ErrorState = ({
  title = "Что-то пошло не так",
  description = "Не получилось загрузить данные. Проверьте связь и попробуйте ещё раз",
  onRetry,
  fill,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  fill?: boolean;
}) => (
  <StateMessage
    fill={fill}
    title={title}
    description={description}
    icon={alertIcon}
    tone="negative"
    action={
      onRetry && (
        <Button size="medium" variant="secondary" onClick={onRetry}>
          Повторить
        </Button>
      )
    }
  />
);

export const LoadingState = ({
  title,
  fill = false,
}: {
  title?: string;
  fill?: boolean;
}) => (
  <Flex
    className={cn(styles.Message, fill && styles.fill)}
    direction="column"
    align="center"
    justify="center"
    gap={12}
    role="status"
  >
    <Spinner size={24} />

    {title && (
      <Typography.Text variant="description" color="secondary">
        {title}
      </Typography.Text>
    )}
  </Flex>
);
