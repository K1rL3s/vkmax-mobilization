import styles from "./fill-bar.module.css";

export const FillBar = ({ share }: { share: number }) => (
  <div className={styles.Track}>
    <div className={styles.Fill} style={{ width: `${share / 100}%` }} />
  </div>
);
