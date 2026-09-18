import { Panel } from "@maxhub/max-ui";

import { ErrorState } from "@/shared/ui/state";

import styles from "./error.module.css";

const ErrorPage = () => {
  return (
    <Panel className={styles.Page} centeredX centeredY>
      <ErrorState fill onRetry={() => window.location.reload()} />
    </Panel>
  );
};

export const Component = ErrorPage;
