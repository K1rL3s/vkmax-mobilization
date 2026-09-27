import { useMount } from "@siberiacancode/reactuse";
import { Outlet } from "react-router-dom";

import { useTrack } from "@/shared/lib/analytics";
import { getMaxLaunch } from "@/shared/lib/max";

import "./globals.css";

import styles from "./app.module.css";

export const App = () => {
  const track = useTrack();

  useMount(() =>
    track({
      type: "miniapp_open",
      source: getMaxLaunch().startParam ? "deeplink" : "direct",
    }),
  );

  return (
    <div className={styles.App}>
      <Outlet />
    </div>
  );
};
