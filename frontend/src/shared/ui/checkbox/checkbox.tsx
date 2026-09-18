import type { ReactNode } from "react";
import { Flex } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { checkIcon, Icon } from "@/shared/ui/icon";

import styles from "./checkbox.module.css";

type CheckboxProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children?: ReactNode;
  disabled?: boolean;
  className?: string;
};

export const Checkbox = ({
  checked,
  onChange,
  children,
  disabled = false,
  className,
}: CheckboxProps) => {
  return (
    <Flex asChild align="flex-start" gap={12}>
      <label
        className={cn(styles.Checkbox, disabled && styles.disabled, className)}
      >
        <input
          type="checkbox"
          className={styles.Input}
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
        />

        <span aria-hidden className={cn(styles.Box, checked && styles.checked)}>
          {checked && <Icon src={checkIcon} size={16} />}
        </span>

        {children && <span className={styles.Label}>{children}</span>}
      </label>
    </Flex>
  );
};
