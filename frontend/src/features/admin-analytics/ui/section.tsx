import type { ReactNode } from "react";
import { Flex, Typography } from "@maxhub/max-ui";

import { ErrorState, LoadingState } from "@/shared/ui/state";

import styles from "./section.module.css";

type SectionProps = {
  title: string;
  note?: string;
  isPending?: boolean;
  isError?: boolean;
  error?: unknown;
  onRetry?: () => void;
  children: ReactNode;
};

export const Section = ({
  title,
  note,
  isPending,
  isError,
  error,
  onRetry,
  children,
}: SectionProps) => (
  <Flex
    className={styles.Section}
    direction="column"
    align="stretch"
    gapY={12}
    asChild
  >
    <section>
      <Flex direction="column" align="stretch" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          {title}
        </Typography.Text>

        {note && (
          <Typography.Text variant="detail" color="tertiary">
            {note}
          </Typography.Text>
        )}
      </Flex>

      {isPending && <LoadingState />}

      {isError && <ErrorState error={error} onRetry={onRetry} />}

      {!isPending && !isError && children}
    </section>
  </Flex>
);
