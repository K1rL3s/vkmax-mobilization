import type { ReactNode } from "react";
import { Button, Flex, Spinner, Typography } from "@maxhub/max-ui";
import { useLocation, useNavigate } from "react-router-dom";

import {
  errorMessage,
  isClientError,
  isUnauthorized,
} from "@/shared/api/errors";
import { cn } from "@/shared/lib/css";
import { getWebApp } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
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
  error,
  onRetry,
  fill,
}: {
  title?: string;
  description?: string;
  error?: unknown;
  onRetry?: () => void;
  fill?: boolean;
}) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const expired = isUnauthorized(error);
  const final = isClientError(error);
  const exit = pathname.startsWith(Routes.ADMIN) ? Routes.ADMIN : Routes.HOME;

  const action = () => {
    if (expired) {
      const webApp = getWebApp();
      return (
        webApp && (
          <Button
            size="medium"
            variant="secondary"
            onClick={() => webApp.close()}
          >
            Закрыть
          </Button>
        )
      );
    }

    if (!final) {
      return (
        onRetry && (
          <Button size="medium" variant="secondary" onClick={onRetry}>
            Повторить
          </Button>
        )
      );
    }

    return (
      fill &&
      pathname !== exit && (
        <Button
          size="medium"
          variant="secondary"
          onClick={() => navigate(exit, { replace: true })}
        >
          На главную
        </Button>
      )
    );
  };

  return (
    <StateMessage
      fill={fill}
      title={expired ? "Сессия устарела" : title}
      description={
        expired
          ? "Закройте приложение и откройте его заново из бота"
          : errorMessage(error, description)
      }
      icon={alertIcon}
      tone="negative"
      action={action()}
    />
  );
};

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
