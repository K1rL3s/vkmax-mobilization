import { cn } from "@/shared/lib/css";
import { Icon } from "@/shared/ui/icon";

import styles from "./icon-tile.module.css";

export type IconTileTone =
  | "neutral"
  | "card"
  | "secondary"
  | "themed"
  | "positive"
  | "negative"
  | "promo";

type IconTileProps = {
  icon: string;
  tone?: IconTileTone;
  size?: "medium" | "large" | "xlarge";
  className?: string;
};

const ICON_SIZE = { medium: 24, large: 24, xlarge: 32 } as const;

export const IconTile = ({
  icon,
  tone = "neutral",
  size = "medium",
  className,
}: IconTileProps) => {
  return (
    <div className={cn(styles.Tile, styles[tone], styles[size], className)}>
      <Icon src={icon} size={ICON_SIZE[size]} />
    </div>
  );
};
