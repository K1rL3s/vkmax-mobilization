import type { ComponentProps } from "react";

import { cn } from "@/shared/lib/css";

import styles from "./card.module.css";

export const Card = ({ className, ...props }: ComponentProps<"div">) => {
  return <div className={cn(styles.Card, className)} {...props} />;
};
