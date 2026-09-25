import type { CSSProperties } from "react";

import { cn } from "@/shared/lib/css";

import styles from "./icon.module.css";

type IconProps = {
  src: string;
  size?: number;
  className?: string;
};

export const Icon = ({ src, size = 24, className }: IconProps) => {
  const style = {
    "--icon-src": `url("${src}")`,
    width: size,
    height: size,
  } as CSSProperties;

  return (
    <span aria-hidden className={cn(styles.Icon, className)} style={style} />
  );
};
