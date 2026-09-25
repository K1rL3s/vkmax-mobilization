import styles from "./fill-bar.module.css";

// доля приезжает в сотых долях процента, ширина считается прямо из неё
export const FillBar = ({ share }: { share: number }) => (
  <div className={styles.Track}>
    <div className={styles.Fill} style={{ width: `${share / 100}%` }} />
  </div>
);
