import { Typography } from "@maxhub/max-ui";

import styles from "./field-error.module.css";

// ошибка поля формы - одна на обе половины продукта: текст под полем красным
// и `role="alert"`, чтобы читалка озвучила его в момент появления
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
