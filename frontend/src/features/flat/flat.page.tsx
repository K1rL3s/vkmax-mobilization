import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link, Navigate } from "react-router-dom";

import { ChargesSection } from "@/features/charges";
import type { ResidencyState } from "@/features/flat-confirmation";
import { FlatResidentsSection } from "@/features/flat-invite";
import { HouseSummary } from "@/features/house";
import { Routes } from "@/shared/model/routes";
import { homeIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { FlatRows } from "./flat-rows";
import { useFlat } from "./use-flat";

import styles from "./flat.module.css";

const actionLabel = (state: ResidencyState) => {
  if (state === "pending") {
    return "Открыть запрос";
  }

  return state === "rejected" ? "Подтвердить ещё раз" : "Подтвердить квартиру";
};

const FlatPage = () => {
  const flat = useFlat();

  if (!flat.residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  const { residency, card, state, canConfirm } = flat;

  const about = () => {
    if (!residency.is_connected) {
      return (
        <Typography.Text variant="description" color="secondary">
          Подтверждение квартиры и счётчики появятся, когда дом подключит УК
        </Typography.Text>
      );
    }

    if (residency.flat_id == null) {
      return residency.flat_number ? (
        <EmptyState
          icon={homeIcon}
          title="Квартиры пока нет в данных УК"
          description="Номер указан вручную. Подтвердить квартиру и передавать показания получится, когда УК заведёт её в системе"
        />
      ) : (
        <EmptyState
          icon={homeIcon}
          title="Квартира не выбрана"
          description="Привяжитесь к дому заново и выберите квартиру - заявки и показания при этом останутся"
        />
      );
    }

    if (card.isPending) {
      return <LoadingState title="Загружаем квартиру" />;
    }

    if (card.isError) {
      return (
        <ErrorState error={card.error} onRetry={() => void card.refetch()} />
      );
    }

    return (
      <div className={styles.Panel}>
        <FlatRows flat={card.data} />
      </div>
    );
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      <HouseSummary
        title={residency.address}
        flat={residency.flat_number}
        state={state}
      />

      {canConfirm && (
        <Button asChild size="medium" stretched>
          <Link
            to={generatePath(Routes.FLAT_CONFIRMATION, {
              residentId: String(residency.resident_id),
            })}
            state={{ returnTo: Routes.FLAT }}
          >
            {actionLabel(state)}
          </Link>
        </Button>
      )}

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>О квартире</h2>
          </Typography.Text>

          {about()}
        </section>
      </Flex>

      <ChargesSection />
      <FlatResidentsSection />
    </Panel>
  );
};

export const Component = FlatPage;
