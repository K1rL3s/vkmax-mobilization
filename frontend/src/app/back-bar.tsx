import { Icon16Chevron, Tappable, Typography } from "@maxhub/max-ui";

import styles from "./back-bar.module.css";

export const BackBar = ({ onBack }: { onBack: () => void }) => (
  <Tappable className={styles.BackBar} onClick={onBack}>
    <span className={styles.Arrow}>
      <Icon16Chevron />
    </span>
    <Typography.Text variant="body" color="inherit">
      Назад
    </Typography.Text>
  </Tappable>
);
