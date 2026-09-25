import { Typography } from "@maxhub/max-ui";

import styles from "./field-error.module.css";

export const FieldError = ({ message }: { message?: string | null }) =>
  message ? (
    <Typography.Text
      className={styles.Error}
      variant="description"
      role="alert"
    >
      {message}
    </Typography.Text>
  ) : null;
