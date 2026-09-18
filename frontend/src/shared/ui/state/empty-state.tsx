import type { ReactNode } from "react";

import { StateMessage } from "./state-message";

type EmptyStateProps = {
  title: string;
  description: string;
  icon?: string;
  action?: ReactNode;
  fill?: boolean;
  className?: string;
};

export const EmptyState = ({
  title,
  description,
  icon,
  action,
  fill = false,
  className,
}: EmptyStateProps) => {
  return (
    <StateMessage
      fill={fill}
      className={className}
      title={title}
      description={description}
      icon={icon}
      action={action}
    />
  );
};
