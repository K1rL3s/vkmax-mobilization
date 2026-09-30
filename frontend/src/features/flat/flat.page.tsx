import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link, Navigate } from "react-router-dom";

import { ChargesSection } from "@/features/charges";
import {
  changeFlatLink,
  confirmationLabel,
  confirmationTone,
  type ResidencyState,
} from "@/features/flat-confirmation";
import { FlatResidentsSection } from "@/features/flat-invite";
import { Routes } from "@/shared/model/routes";
import { homeIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

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
      return (
        <EmptyState
          icon={homeIcon}
          title={
            residency.flat_number
              ? "Квартиры пока нет в данных УК"
              : "Квартира не выбрана"
          }
          description={
            residency.flat_number
              ? "Номер указан вручную. Подтвердить квартиру и передавать показания получится, когда УК заведёт её в системе. Если номер указан с ошибкой, исправьте его"
              : "Укажите номер квартиры, чтобы подтвердить её и передавать показания"
          }
          action={
            <Button asChild size="medium" variant="secondary">
              <Link {...changeFlatLink(residency, Routes.FLAT)}>
                {residency.flat_number
                  ? "Изменить номер квартиры"
                  : "Указать квартиру"}
              </Link>
            </Button>
          }
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
      <Flex align="stretch" direction="column" gapY={12}>
        <Flex align="stretch" direction="column" gapY={4}>
          <Typography.Text asChild variant="header" color="primary">
            <h1 className={styles.Address}>{residency.address}</h1>
          </Typography.Text>
          <Flex align="center" gap={8} wrap="wrap">
            {residency.flat_number && (
              <Typography.Text variant="description" color="secondary">
                кв. {residency.flat_number}
              </Typography.Text>
            )}
            <StatusPill tone={confirmationTone(state)}>
              {confirmationLabel(state)}
            </StatusPill>
          </Flex>
        </Flex>

        <Flex>
          <Button asChild size="small" variant="secondary">
            <Link to={Routes.RESIDENCIES}>Сменить дом</Link>
          </Button>
        </Flex>
      </Flex>

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
