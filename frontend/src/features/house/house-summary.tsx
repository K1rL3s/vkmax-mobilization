import type { ElementType, ReactNode } from "react";
import { Flex, Tappable, Typography } from "@maxhub/max-ui";

import {
  confirmationCaption,
  type ResidencyState,
} from "@/features/flat-confirmation";
import { Chevron } from "@/shared/ui/chevron";
import { homeIcon } from "@/shared/ui/icon";
import { IconTile, type IconTileTone } from "@/shared/ui/icon-tile";

import styles from "./house-summary.module.css";

type HouseSummaryState = ResidencyState | "plain";

const TONE: Record<HouseSummaryState, IconTileTone> = {
  verified: "brand-green",
  pending: "brand-blue",
  ways: "brand-orange",
  rejected: "brand-orange",
  "no-flat": "brand-orange",
  "flat-missing": "brand-orange",
  "not-connected": "neutral",
  plain: "brand-blue",
};

type HouseSummaryProps = {
  title: string;
  as?: ElementType;
  onClick?: () => void;
} & (
  | { state: ResidencyState; flat?: string | null; subtitle?: never }
  | { state: "plain"; flat?: never; subtitle?: ReactNode }
);

export const HouseSummary = ({
  title,
  as: Title = "div",
  onClick,
  state,
  flat,
  subtitle,
}: HouseSummaryProps) => {
  const caption =
    state === "plain"
      ? subtitle
      : [flat && `кв. ${flat}`, confirmationCaption(state)]
          .filter(Boolean)
          .join(" · ");

  const content = (
    <>
      <IconTile icon={homeIcon} tone={TONE[state]} size="large" />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={2}>
        <Typography.Text
          asChild
          variant="title"
          color="primary"
          className={styles.Ellipsis}
        >
          <Title>{title}</Title>
        </Typography.Text>

        {caption && (
          <Typography.Text variant="description" color="secondary">
            {caption}
          </Typography.Text>
        )}
      </Flex>

      {onClick && <Chevron />}
    </>
  );

  if (onClick) {
    return (
      <Tappable className={styles.Summary} onClick={onClick}>
        {content}
      </Tappable>
    );
  }

  return <div className={styles.Summary}>{content}</div>;
};
