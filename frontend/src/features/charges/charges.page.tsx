import { Panel, Typography } from "@maxhub/max-ui";
import { Navigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";

import { ChargesList, ModelNote } from "./charges-section";
import { useCharges } from "./use-charges";

import styles from "./charges.module.css";

const ChargesPage = () => {
  const { access } = useCharges();

  if (access === "none") {
    return <Navigate to={Routes.FLAT} replace />;
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text asChild variant="title" color="primary">
        <h1>История начислений</h1>
      </Typography.Text>

      <ChargesList page />

      <ModelNote text="Начисления - модельные данные для демонстрации" />
    </Panel>
  );
};

export const Component = ChargesPage;
