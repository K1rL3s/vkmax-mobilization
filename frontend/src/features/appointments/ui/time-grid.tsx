import { Button, Flex, Typography } from "@maxhub/max-ui";

import type { ReceptionSlot, Schedule } from "../domain/schedule";

import styles from "./time-grid.module.css";

type TimeGridProps = {
  groups: { title: string | null; slots: ReceptionSlot[] }[];
  value: string | undefined;
  schedule: Schedule;
  isOwn: (slot: ReceptionSlot) => boolean;
  onChange: (startsAt: string) => void;
};

export const TimeGrid = ({
  groups,
  value,
  schedule,
  isOwn,
  onChange,
}: TimeGridProps) => {
  return (
    <Flex direction="column" align="stretch" gap={12}>
      {groups.map((group) => (
        <Flex
          key={group.title ?? "all"}
          direction="column"
          align="stretch"
          gap={8}
        >
          {group.title && (
            <Typography.Text variant="description" color="secondary">
              {group.title}
            </Typography.Text>
          )}

          <div className={styles.Grid}>
            {group.slots.map((slot) => {
              const time = schedule.slotTime(slot.starts_at);
              const own = isOwn(slot);

              return (
                <Button
                  key={slot.starts_at}
                  size="medium"
                  className={styles.Slot}
                  variant={slot.starts_at === value ? "primary" : "secondary"}
                  disabled={!slot.is_free || own}
                  aria-pressed={slot.starts_at === value}
                  aria-label={
                    own
                      ? `${time}, ваша запись`
                      : slot.is_free
                        ? time
                        : `${time}, занято`
                  }
                  onClick={() => onChange(slot.starts_at)}
                >
                  {time}
                </Button>
              );
            })}
          </div>
        </Flex>
      ))}
    </Flex>
  );
};
