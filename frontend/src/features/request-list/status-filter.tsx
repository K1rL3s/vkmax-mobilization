import { Button } from "@maxhub/max-ui";

import { FILTERS, type FilterId } from "./filters";

import styles from "./status-filter.module.css";

type StatusFilterProps = {
  value: FilterId;
  onChange: (value: FilterId) => void;
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
