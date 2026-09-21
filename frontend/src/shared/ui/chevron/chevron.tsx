import { chevronSmallIcon, Icon } from "@/shared/ui/icon";

import styles from "./chevron.module.css";

export const Chevron = () => (
  <Icon src={chevronSmallIcon} size={12} className={styles.Chevron} />
);
