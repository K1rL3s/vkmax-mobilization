import { Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";

import styles from "./time-chips.module.css";

export const TimeChips = ({
  labels,
  inCard,
}: {
  labels: string[];
  inCard?: boolean;
}) => (
  <div className={styles.TimeChips}>
    {labels.map((label) => (
      <Typography.Text
        key={label}
        className={cn(styles.Chip, inCard && styles.inCard)}
        variant="description"
        color="primary"
      >
        {label}
      </Typography.Text>
    ))}
  </div>
);
