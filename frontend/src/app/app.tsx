import { Outlet } from "react-router-dom";

import "@maxhub/max-ui/dist/styles.css";

import styles from "./app.module.css";

export const App = () => {
  return (
    <div className={styles.App}>
      <Outlet />
    </div>
  );
};
