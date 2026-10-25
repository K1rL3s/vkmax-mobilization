import { useState } from "react";
import { Button, CellSimple, Flex, Radio, Typography } from "@maxhub/max-ui";

import type { RequestPlace } from "@/features/request";
import { cn } from "@/shared/lib/css";
import { haptic } from "@/shared/lib/max";
import { BottomSheet } from "@/shared/ui/bottom-sheet";

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

type EntranceChoiceProps = {
  count: number;
  value: number | null;
  onChange: (value: number | null) => void;
};

export const EntranceChoice = ({
  count,
  value,
  onChange,
}: EntranceChoiceProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const label = (entrance: number | null) =>
    entrance === null ? "Не указан" : `Подъезд ${entrance}`;

  return (
    <>
      <div className={styles.Panel}>
        <CellSimple
          title={label(value)}
          showChevron
          onClick={() => setIsOpen(true)}
        />
      </div>

      <BottomSheet isOpen={isOpen} onClose={() => setIsOpen(false)}>
        <Flex direction="column" align="stretch" gapY={12}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.SheetTitle}>В каком подъезде?</h2>
          </Typography.Text>

          <div className={styles.Panel}>
            {[
              null,
              ...Array.from({ length: count }, (_, index) => index + 1),
            ].map((entrance, index) => (
              <CellSimple
                key={entrance ?? "none"}
                as="label"
                separator={index > 0}
                title={label(entrance)}
                after={
                  <Radio
                    name="request-entrance"
                    checked={entrance === value}
                    onChange={() => {
                      haptic.select();
                      onChange(entrance);
                      setIsOpen(false);
                    }}
                  />
                }
              />
            ))}
          </div>

          <Button
            size="large"
            variant="secondary"
            stretched
            onClick={() => setIsOpen(false)}
          >
            Отмена
          </Button>
        </Flex>
      </BottomSheet>
    </>
  );
};
