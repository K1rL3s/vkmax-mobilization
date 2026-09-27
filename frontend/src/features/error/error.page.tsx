import { Panel } from "@maxhub/max-ui";
import { useRevalidator, useRouteError } from "react-router-dom";

import { ErrorState } from "@/shared/ui/state";

import styles from "./error.module.css";

const ErrorPage = () => {
  const error = useRouteError();
  const revalidator = useRevalidator();

  return (
    <Panel className={styles.Page} centeredX centeredY>
      <ErrorState
        fill
        error={error}
        onRetry={() => void revalidator.revalidate()}
      />
    </Panel>
  );
};

export const Component = ErrorPage;
