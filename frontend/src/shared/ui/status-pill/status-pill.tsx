import { Typography } from "@maxhub/max-ui";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/css";

import styles from "./status-pill.module.css";

export type StatusPillTone =
  "themed" | "promo" | "neutral" | "positive" | "negative";

type StatusPillProps = {
  tone: StatusPillTone;
  children: ReactNode;
};

export const StatusPill = ({ tone, children }: StatusPillProps) => (
  <Typography.Text
    className={cn(styles.StatusPill, styles[tone])}
    variant="label-strong"
  >
    {children}
  </Typography.Text>
);
