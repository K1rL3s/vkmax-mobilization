import { Button } from "@maxhub/max-ui";

import { PERIODS, type PeriodDays } from "../domain/period";

import styles from "./period-chips.module.css";

type PeriodChipsProps = {
  value: PeriodDays;
  onChange: (value: PeriodDays) => void;
};

export const PeriodChips = ({ value, onChange }: PeriodChipsProps) => (
  <div className={styles.Chips}>
    {PERIODS.map((days) => (
      <Button
        key={days}
        size="small"
        variant={days === value ? "primary" : "secondary"}
        aria-pressed={days === value}
        onClick={() => onChange(days)}
      >
        {days} дней
      </Button>
    ))}
  </div>
);
