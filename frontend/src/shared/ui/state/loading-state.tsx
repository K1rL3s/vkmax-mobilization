import { Flex, Spinner, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";

import styles from "./state-message.module.css";

type LoadingStateProps = {
  title?: string;
  fill?: boolean;
  className?: string;
};

export const LoadingState = ({
  title,
  fill = false,
  className,
}: LoadingStateProps) => {
  return (
    <Flex
      className={cn(styles.Message, fill && styles.fill, className)}
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
};
