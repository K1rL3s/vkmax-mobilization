import { cn } from "@/shared/lib/css";
import { Icon, starFilledIcon, starIcon } from "@/shared/ui/icon";

import styles from "./rating-stars.module.css";

type RatingStarsProps = {
  value: number;
  onChange?: (value: number) => void;
};

export const RatingStars = ({ value, onChange }: RatingStarsProps) => (
  <div className={styles.Stars}>
    {[1, 2, 3, 4, 5].map((star) => {
      const filled = star <= value;
      const icon = (
        <Icon
          src={filled ? starFilledIcon : starIcon}
          size={32}
          className={cn(styles.Star, filled && styles.filled)}
        />
      );

      return onChange ? (
        <button
          key={star}
          className={styles.Button}
          type="button"
          aria-label={`Оценка ${star} из 5`}
          aria-pressed={filled}
          onClick={() => onChange(star)}
        >
          {icon}
        </button>
      ) : (
        <span key={star}>{icon}</span>
      );
    })}
  </div>
);
