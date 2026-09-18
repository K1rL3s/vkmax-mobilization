import { Button } from "@maxhub/max-ui";

import { alertIcon } from "@/shared/ui/icon";

import { StateMessage } from "./state-message";

type ErrorStateProps = {
  title?: string;
  description?: string;
  onRetry?: () => void;
  fill?: boolean;
  className?: string;
};

export const ErrorState = ({
  title = "Что-то пошло не так",
  description = "Не получилось загрузить данные. Проверьте связь и попробуйте ещё раз",
  onRetry,
  fill = false,
  className,
}: ErrorStateProps) => {
  return (
    <StateMessage
      fill={fill}
      className={className}
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
};
