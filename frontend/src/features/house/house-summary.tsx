import type { ElementType, ReactNode } from "react";
import { Flex, Tappable, Typography } from "@maxhub/max-ui";

import {
  confirmationLabel,
  confirmationTone,
  type ResidencyState,
} from "@/features/flat-confirmation";
import { Chevron } from "@/shared/ui/chevron";
import { homeIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { StatusPill } from "@/shared/ui/status-pill";

import styles from "./house-summary.module.css";

type HouseSummaryProps = {
  title: string;
  as?: ElementType;
  action?: string;
  onClick?: () => void;
} & (
  | { state: ResidencyState; flat?: string | null; subtitle?: never }
  | { state: "plain"; flat?: never; subtitle?: ReactNode }
);

export const HouseSummary = ({
  title,
  as: Title = "div",
  action,
  onClick,
  state,
  flat,
  subtitle,
}: HouseSummaryProps) => {
  const tone = state === "plain" ? "themed" : confirmationTone(state);

  const caption =
    state === "plain" ? (
      subtitle
    ) : (
      <Flex align="center" gap={8} wrap="wrap">
        {flat && (
          <Typography.Text variant="description" color="secondary">
            кв. {flat}
          </Typography.Text>
        )}
        <StatusPill tone={tone}>{confirmationLabel(state)}</StatusPill>
      </Flex>
    );

  const content = (
    <>
      <IconTile icon={homeIcon} tone={tone} />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={2}>
        <Typography.Text
          asChild
          variant="title"
          color="primary"
          className={styles.Ellipsis}
        >
          <Title>{title}</Title>
        </Typography.Text>

        {caption &&
          (state === "plain" ? (
            <Typography.Text variant="description" color="secondary">
              {caption}
            </Typography.Text>
          ) : (
            caption
          ))}

        {action && (
          <Typography.Text className={styles.Action} variant="detail-strong">
            {action}
          </Typography.Text>
        )}
      </Flex>

      {onClick && <Chevron />}
    </>
  );

  if (!onClick) {
    return <div className={styles.Summary}>{content}</div>;
  }

  return (
    <Tappable className={styles.Summary} onClick={onClick}>
      {content}
    </Tappable>
  );
};
