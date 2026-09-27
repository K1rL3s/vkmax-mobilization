import { Panel } from "@maxhub/max-ui";
import { useRouteError } from "react-router-dom";

import { ErrorState } from "@/shared/ui/state";

import styles from "./error.module.css";

const ErrorPage = () => {
  const error = useRouteError();

  return (
    <Panel className={styles.Page} centeredX centeredY>
      <ErrorState fill error={error} onRetry={() => window.location.reload()} />
    </Panel>
  );
};

export const Component = ErrorPage;
