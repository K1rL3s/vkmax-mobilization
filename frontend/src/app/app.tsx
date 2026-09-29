import { useLayoutEffect } from "react";
import { useMount } from "@siberiacancode/reactuse";
import { Outlet, ScrollRestoration } from "react-router-dom";

import { useTrack } from "@/shared/lib/analytics";
import { getMaxLaunch } from "@/shared/lib/max";
import { useTextSize } from "@/shared/model/session";

import "./globals.css";

import styles from "./app.module.css";

export const App = () => {
  const track = useTrack();
  const textSize = useTextSize();

  useMount(() =>
    track({
      type: "miniapp_open",
      source: getMaxLaunch().startParam ? "deeplink" : "direct",
    }),
  );

  useLayoutEffect(() => {
    document.documentElement.dataset.textSize = textSize;
  }, [textSize]);

  return (
    <div className={styles.Frame}>
      <div className={styles.App}>
        <Outlet />
      </div>
      <ScrollRestoration />
    </div>
  );
};
