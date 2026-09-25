import { Button } from "@maxhub/max-ui";

import type { RequestCategory, RequestCategoryItem } from "@/features/request";

import styles from "./category-chips.module.css";

type CategoryChipsProps = {
  categories: RequestCategoryItem[];
  value: RequestCategory | null;
  onChange: (value: RequestCategory) => void;
};

export const CategoryChips = ({
  categories,
  value,
  onChange,
}: CategoryChipsProps) => (
  <div className={styles.Chips}>
    {categories.map((item) => (
      <Button
        key={item.category}
        size="small"
        variant={item.category === value ? "primary" : "secondary"}
        aria-pressed={item.category === value}
        onClick={() => onChange(item.category)}
      >
        {item.label}
      </Button>
    ))}
  </div>
);
