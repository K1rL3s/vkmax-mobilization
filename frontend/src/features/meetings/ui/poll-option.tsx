import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { formatPercent } from "@/shared/lib/format";
import { checkIcon, Icon } from "@/shared/ui/icon";

import { flatsCount, type PollCard, type PollResults } from "../domain/poll";

import styles from "./poll-option.module.css";

type PollOptionProps = {
  option: PollCard["options"][number];
  result: PollResults["options"][number] | undefined;
  isMine: boolean;
  isSelected: boolean;
  isMultiple: boolean;
  selectable: boolean;
  onToggle: () => void;
};

export const PollOption = ({
  option,
  result,
  isMine,
  isSelected,
  isMultiple,
  selectable,
  onToggle,
}: PollOptionProps) => {
  const percent = result ? result.area_percent / 100 : 0;

  const body = (
    <>
      <Flex align="center" gap={8}>
        {selectable && (
          <span
            className={cn(
              styles.Marker,
              isMultiple && styles.square,
              isSelected && styles.checked,
            )}
          />
        )}

        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          {option.text}
        </Typography.Text>

        {isMine && <Icon className={styles.Mine} src={checkIcon} size={16} />}
      </Flex>

      <div className={styles.Track}>
        <div className={styles.Fill} style={{ width: `${percent}%` }} />
      </div>

      <Typography.Text variant="description" color="secondary">
        {flatsCount(result?.flats_count ?? 0)} ·{" "}
        {formatPercent(result?.area_percent ?? 0)} площади дома
      </Typography.Text>
    </>
  );

  if (!selectable) {
    return (
      <div className={cn(styles.Option, isMine && styles.mine)}>{body}</div>
    );
  }

  return (
    <label className={cn(styles.Option, isSelected && styles.selected)}>
      <input
        className={styles.Control}
        type={isMultiple ? "checkbox" : "radio"}
        name="poll-option"
        checked={isSelected}
        onChange={onToggle}
      />
      {body}
    </label>
  );
};
