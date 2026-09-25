import { Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";

import { weekdayLabel, type ReceptionDay } from "../domain/schedule";

import styles from "./day-chips.module.css";

type DayChipsProps = {
  days: ReceptionDay[];
  value: string | undefined;
  onChange: (key: string) => void;
};

export const DayChips = ({ days, value, onChange }: DayChipsProps) => (
  <div className={styles.Scroller}>
    {days.map((day) => (
      <button
        key={day.key}
        type="button"
        className={cn(styles.Day, day.key === value && styles.selected)}
        disabled={day.slots.length === 0}
        aria-pressed={day.key === value}
        onClick={() => onChange(day.key)}
      >
        <Typography.Text variant="description">
          {weekdayLabel(day.date)}
        </Typography.Text>
        <Typography.Text variant="title">
          {day.date.getUTCDate()}
        </Typography.Text>
      </button>
    ))}
  </div>
);
