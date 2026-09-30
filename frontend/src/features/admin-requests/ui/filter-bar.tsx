import { useState } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";

import { BottomSheet } from "@/shared/ui/bottom-sheet";
import { chevronSmallIcon, Icon } from "@/shared/ui/icon";

import { ChipRow } from "./chip-row";

import styles from "./filter-bar.module.css";

export type FilterGroup<N extends string> = {
  name: N;
  label: string;
  options: readonly { id: string; label: string }[];
  value: string;
  defaultValue?: string;
};

export const FilterBar = <N extends string>({
  groups,
  onChange,
  onReset,
}: {
  groups: FilterGroup<N>[];
  onChange: (name: N, value: string) => void;
  onReset?: () => void;
}) => {
  const [openName, setOpenName] = useState<N | null>(null);
  const open = groups.find((group) => group.name === openName);

  return (
    <>
      <div className={styles.FilterBar}>
        {groups.map((group) => (
          <Button
            key={group.name}
            type="button"
            size="small"
            variant={
              group.value === (group.defaultValue ?? "all")
                ? "secondary"
                : "primary"
            }
            aria-haspopup="dialog"
            iconAfter={
              <Icon src={chevronSmallIcon} size={12} className={styles.Down} />
            }
            onClick={() => setOpenName(group.name)}
          >
            {group.label}:{" "}
            {group.options.find((option) => option.id === group.value)?.label ??
              group.value}
          </Button>
        ))}
        {onReset && (
          <Button
            type="button"
            size="small"
            variant="secondary"
            onClick={onReset}
          >
            Сбросить
          </Button>
        )}
      </div>

      <BottomSheet
        isOpen={open !== undefined}
        onClose={() => setOpenName(null)}
      >
        {open && (
          <Flex direction="column" align="stretch" gapY={16}>
            <Typography.Text asChild variant="title" color="primary">
              <h2 className={styles.Title}>{open.label}</h2>
            </Typography.Text>
            <ChipRow
              label={open.label}
              options={open.options}
              value={open.value}
              wrap
              onChange={(id) => {
                onChange(open.name, id);
                setOpenName(null);
              }}
            />
            <Button
              size="large"
              variant="secondary"
              stretched
              onClick={() => setOpenName(null)}
            >
              Отмена
            </Button>
          </Flex>
        )}
      </BottomSheet>
    </>
  );
};
