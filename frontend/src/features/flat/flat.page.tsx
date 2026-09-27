import { Button, Flex, Panel, Tappable, Typography } from "@maxhub/max-ui";
import { generatePath, Link, Navigate, useNavigate } from "react-router-dom";

import { ChargesSection } from "@/features/charges";
import type { ConfirmationView } from "@/features/flat-confirmation";
import { FlatResidentsSection } from "@/features/flat-invite";
import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { homeIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { FlatRows } from "./flat-rows";
import { useFlat } from "./use-flat";

import styles from "./flat.module.css";

const actionLabel = (view: ConfirmationView) => {
  if (view === "pending") {
    return "Открыть запрос";
  }

  return view === "rejected" ? "Подтвердить ещё раз" : "Подтвердить квартиру";
};

const FlatPage = () => {
  const navigate = useNavigate();
  const flat = useFlat();

  if (!flat.residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  const { residency, card, view, canConfirm, caption, title } = flat;

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
      <Flex asChild align="center" gap={12}>
        <Tappable
          className={styles.Summary}
          onClick={() => void navigate(Routes.RESIDENCIES)}
        >
          <IconTile
            icon={homeIcon}
            tone={residency.verified ? "positive" : "themed"}
            size="large"
          />
          <Flex
            className={styles.Grow}
            align="stretch"
            direction="column"
            gapY={2}
          >
            <Typography.Text variant="title" color="primary">
              {title}
            </Typography.Text>
            <Typography.Text
              variant="description"
              color="secondary"
              className={styles.Ellipsis}
            >
              {residency.address}
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              {caption}
            </Typography.Text>
          </Flex>
          <Chevron />
        </Tappable>
      </Flex>

      {canConfirm && (
        <Button asChild size="medium" stretched>
          <Link
            to={generatePath(Routes.FLAT_CONFIRMATION, {
              residentId: String(residency.resident_id),
            })}
            state={{ returnTo: Routes.FLAT }}
          >
            {actionLabel(view)}
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
