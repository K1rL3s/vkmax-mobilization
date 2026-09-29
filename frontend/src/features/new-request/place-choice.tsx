import { Typography } from "@maxhub/max-ui";

import type { RequestPlace } from "@/features/request";
import { cn } from "@/shared/lib/css";
import { haptic } from "@/shared/lib/max";

import styles from "./place-choice.module.css";

type PlaceChoiceProps = {
  value: RequestPlace | null;
  onChange: (value: RequestPlace) => void;
};

export const PlaceChoice = ({ value, onChange }: PlaceChoiceProps) => (
  <div className={styles.Panel} role="radiogroup" aria-label="Где проблема?">
    {(
      [
        { id: "flat", title: "🏠 В моей квартире" },
        { id: "house", title: "🏢 В доме: подъезд, двор, общее имущество" },
      ] as const
    ).map((option) => (
      <label key={option.id} className={styles.Option}>
        <input
          className={styles.Control}
          type="radio"
          name="request-place"
          checked={option.id === value}
          onChange={() => {
            haptic.select();
            onChange(option.id);
          }}
        />
        <Typography.Text className={styles.Grow} variant="body" color="primary">
          {option.title}
        </Typography.Text>
        <span
          className={cn(styles.Marker, option.id === value && styles.checked)}
        />
      </label>
    ))}
  </div>
);
