import { Button } from "@maxhub/max-ui";

import type { StatusFilterId } from "../model/use-verification-list";

import styles from "./status-filter.module.css";

const FILTERS: { id: StatusFilterId; label: string }[] = [
  { id: "all", label: "Все" },
  { id: "pending", label: "Ждут решения" },
  { id: "decided", label: "Решённые" },
];

type StatusFilterProps = {
  value: StatusFilterId;
  onChange: (value: StatusFilterId) => void;
};

export const StatusFilter = ({ value, onChange }: StatusFilterProps) => {
  return (
    <div className={styles.Filter} role="tablist">
      {FILTERS.map((filter) => (
        <Button
          key={filter.id}
          role="tab"
          aria-selected={filter.id === value}
          size="small"
          variant={filter.id === value ? "primary" : "secondary"}
          onClick={() => onChange(filter.id)}
        >
          {filter.label}
        </Button>
      ))}
    </div>
  );
};
