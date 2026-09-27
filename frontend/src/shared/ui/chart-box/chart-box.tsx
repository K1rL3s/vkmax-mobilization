import type { ReactNode } from "react";
import { ResponsiveContainer } from "recharts";

import styles from "./chart-box.module.css";

export const ChartBox = ({
  height,
  children,
}: {
  height: number;
  children: ReactNode;
}) => (
  <div className={styles.Box}>
    <ResponsiveContainer width="100%" height={height}>
      {children}
    </ResponsiveContainer>
  </div>
);
