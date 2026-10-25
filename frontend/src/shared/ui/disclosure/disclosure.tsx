import { type ReactNode, useState } from "react";
import { Typography } from "@maxhub/max-ui";

import { Chevron } from "@/shared/ui/chevron";

import styles from "./disclosure.module.css";

export const Disclosure = ({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) => {
  const [open, setOpen] = useState(false);

  return (
    <details
      className={styles.Disclosure}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className={styles.Title}>
        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          {title}
        </Typography.Text>
        <span className={styles.Chevron}>
          <Chevron />
        </span>
      </summary>
      {open && children}
    </details>
  );
};
