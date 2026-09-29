import { Tappable, Typography } from "@maxhub/max-ui";

import { Icon } from "@/shared/ui/icon";

import styles from "./strip-button.module.css";

export const StripButton = ({
  icon,
  label,
  onClick,
}: {
  icon: string;
  label: string;
  onClick: () => void;
}) => (
  <Tappable className={styles.StripButton} onClick={onClick}>
    <Icon src={icon} size={16} />
    <Typography.Text variant="tag" color="primary">
      {label}
    </Typography.Text>
  </Tappable>
);
