import { Button } from "@maxhub/max-ui";

import { haptic } from "@/shared/lib/max";

import { METER_LABEL, type Meter } from "../domain/reading";

import styles from "./meter-chips.module.css";

type MeterChipsProps = {
  meters: Meter[];
  value: number | undefined;
  onChange: (meterId: number) => void;
};

export const MeterChips = ({ meters, value, onChange }: MeterChipsProps) => {
  return (
    <div className={styles.Chips}>
      {meters.map((meter) => (
        <Button
          key={meter.id}
          size="small"
          variant={meter.id === value ? "primary" : "secondary"}
          aria-pressed={meter.id === value}
          onClick={() => {
            if (meter.id !== value) {
              haptic.select();
            }
            onChange(meter.id);
          }}
        >
          {METER_LABEL[meter.type]}
        </Button>
      ))}
    </div>
  );
};
