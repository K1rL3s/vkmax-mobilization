import { Flex, Panel, Typography } from "@maxhub/max-ui";
import { Navigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { receiptIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { ChargeRows, ChargesGate, ModelNote } from "./charges-section";
import { useCharges } from "./use-charges";

import styles from "./charges.module.css";

const ChargesPage = () => {
  const { access, list } = useCharges();

  if (access === "none") {
    return <Navigate to={Routes.FLAT} replace />;
  }

  const content = () => {
    if (access !== "open") {
      return <ChargesGate />;
    }

    if (list.isPending) {
      return <LoadingState fill title="Загружаем начисления" />;
    }

    if (list.isError) {
      return <ErrorState fill onRetry={() => void list.refetch()} />;
    }

    if (list.data.items.length === 0) {
      return (
        <EmptyState
          fill
          icon={receiptIcon}
          title="Начислений пока нет"
          description="Квитанция появится здесь, когда УК закроет первый месяц"
        />
      );
    }

    return (
      <Flex align="stretch" direction="column" gap={8}>
        <ChargeRows items={list.data.items} />
        <Typography.Text variant="description" color="secondary">
          Откройте месяц, чтобы увидеть, что изменилось: тариф или расход
        </Typography.Text>
      </Flex>
    );
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      <Typography.Text asChild variant="title" color="primary">
        <h1>История начислений</h1>
      </Typography.Text>

      {content()}

      <ModelNote text="Начисления - модельные данные для демонстрации" />
    </Panel>
  );
};

export const Component = ChargesPage;
