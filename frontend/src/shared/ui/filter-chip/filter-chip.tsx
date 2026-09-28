import type { ReactNode } from "react";
import { Typography } from "@maxhub/max-ui";

import { closeIcon, Icon } from "@/shared/ui/icon";

import styles from "./filter-chip.module.css";

export const FilterChip = ({
  children,
  onRemove,
}: {
  children: ReactNode;
  onRemove: () => void;
}) => (
  <button type="button" className={styles.FilterChip} onClick={onRemove}>
    <Typography.Text variant="body" color="primary">
      {children}
    </Typography.Text>
    <Icon src={closeIcon} size={16} className={styles.Close} />
  </button>
);
