import { Button } from "@maxhub/max-ui";

import styles from "./chip-row.module.css";

type ChipRowProps<T extends string> = {
  label: string;
  options: readonly { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
  disabled?: boolean;
  wrap?: boolean;
};

export const ChipRow = <T extends string>({
  label,
  options,
  value,
  onChange,
  disabled,
  wrap,
}: ChipRowProps<T>) => (
  <div
    className={wrap ? styles.Wrapped : styles.Row}
    role="radiogroup"
    aria-label={label}
  >
    {options.map((option) => (
      <Button
        key={option.id}
        type="button"
        role="radio"
        aria-checked={option.id === value}
        size="small"
        variant={option.id === value ? "primary" : "secondary"}
        disabled={disabled}
        onClick={() => onChange(option.id)}
      >
        {option.label}
      </Button>
    ))}
  </div>
);
