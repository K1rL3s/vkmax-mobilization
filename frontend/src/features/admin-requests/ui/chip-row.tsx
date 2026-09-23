import { Button } from "@maxhub/max-ui";

import styles from "./chip-row.module.css";

type ChipRowProps = {
  label: string;
  options: readonly { id: string; label: string }[];
  value: string | null;
  onChange: (id: string) => void;
  disabled?: boolean;
  wrap?: boolean;
};

export const ChipRow = ({
  label,
  options,
  value,
  onChange,
  disabled,
  wrap = false,
}: ChipRowProps) => (
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
