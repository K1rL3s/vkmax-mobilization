import { Button } from "@maxhub/max-ui";

import type { RequestCategory, RequestCategoryItem } from "@/features/request";
import { haptic } from "@/shared/lib/max";

import styles from "./category-chips.module.css";

type CategoryChipsProps = {
  categories: RequestCategoryItem[];
  value: RequestCategory | null;
  suggested: RequestCategory | null;
  onChange: (value: RequestCategory) => void;
};

export const CategoryChips = ({
  categories,
  value,
  suggested,
  onChange,
}: CategoryChipsProps) => (
  <div className={styles.Chips}>
    {categories.map((item) => (
      <Button
        key={item.category}
        size="small"
        variant={item.category === value ? "primary" : "secondary"}
        aria-pressed={item.category === value}
        onClick={() => {
          if (item.category !== value) {
            haptic.select();
          }
          onChange(item.category);
        }}
      >
        {item.label}
        {item.category === suggested && (
          <span className={styles.Suggested}>подсказка</span>
        )}
      </Button>
    ))}
  </div>
);
