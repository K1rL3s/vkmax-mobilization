import { Button, CellSimple, Flex, Typography } from "@maxhub/max-ui";
import { generatePath, Link, useNavigate } from "react-router-dom";

import { confirmationView } from "@/features/flat-confirmation";
import { Routes } from "@/shared/model/routes";
import { Icon, infoIcon, receiptIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { formatMoney, formatPeriod, listDelta } from "./charge";
import { useCharges } from "./use-charges";

import styles from "./charges-section.module.css";

const SECTION_ROWS = 3;

export const ModelNote = ({ text }: { text: string }) => (
  <Flex align="center" gap={12} className={styles.Note}>
    <Icon src={infoIcon} size={24} className={styles.NoteIcon} />
    <Typography.Text variant="description" color="secondary">
      {text}
    </Typography.Text>
  </Flex>
);

export const ChargesList = ({ page = false }: { page?: boolean }) => {
  const navigate = useNavigate();
  const { residency, access, list } = useCharges();

  if (access === "tenant") {
    return (
      <EmptyState
        icon={receiptIcon}
        title="Начисления видит собственник"
        description="Арендатору они закрыты намеренно: квитанции, суммы и лицевой счёт остаются у владельца квартиры"
      />
    );
  }

  if (access === "unverified" && residency) {
    const view = confirmationView(residency);
    const isPending = view === "pending";

    return (
      <EmptyState
        icon={receiptIcon}
        title={
          isPending
            ? "Ждём подтверждения квартиры"
            : "Подтвердите квартиру, чтобы видеть начисления"
        }
        description={
          isPending
            ? "УК проверяет запрос. Начисления откроются, как только квартиру подтвердят"
            : "Квитанции показываем только подтверждённому собственнику"
        }
        action={
          <Button asChild size="medium" variant="secondary">
            <Link
              to={generatePath(Routes.FLAT_CONFIRMATION, {
                residentId: String(residency.resident_id),
              })}
              state={{ returnTo: Routes.FLAT }}
            >
              {isPending && "Открыть запрос"}
              {view === "rejected" && "Подтвердить ещё раз"}
              {!isPending && view !== "rejected" && "Подтвердить квартиру"}
            </Link>
          </Button>
        }
      />
    );
  }

  if (list.isPending) {
    return <LoadingState fill={page} title="Загружаем начисления" />;
  }

  if (list.isError) {
    return <ErrorState fill={page} onRetry={() => void list.refetch()} />;
  }

  if (list.data.items.length === 0) {
    return (
      <EmptyState
        fill={page}
        icon={receiptIcon}
        title="Начислений пока нет"
        description="Квитанция появится здесь, когда УК закроет первый месяц"
      />
    );
  }

  const { items, total } = list.data;
  const rows = (
    <>
      <div className={styles.Panel}>
        {items.slice(0, page ? undefined : SECTION_ROWS).map((item, index) => (
          <CellSimple
            key={item.id}
            separator={index > 0}
            title={formatPeriod(item.period)}
            subtitle={[
              listDelta(item, items[index + 1]),
              item.paid_at && "оплачено",
            ]
              .filter(Boolean)
              .join(" · ")}
            after={
              <Typography.Text
                variant="body"
                color="secondary"
                className={styles.Amount}
              >
                {formatMoney(item.total)}
              </Typography.Text>
            }
            showChevron
            onClick={() =>
              void navigate(
                generatePath(Routes.CHARGE, { chargeId: String(item.id) }),
              )
            }
          />
        ))}

        {!page && total > SECTION_ROWS && (
          <CellSimple
            separator
            title="Вся история"
            after={
              <Typography.Text
                variant="body"
                color="secondary"
                className={styles.Amount}
              >
                {total}
              </Typography.Text>
            }
            showChevron
            onClick={() => void navigate(Routes.CHARGES)}
          />
        )}
      </div>
      <Typography.Text variant="description" color="secondary">
        Откройте месяц, чтобы увидеть, что изменилось: тариф или расход
      </Typography.Text>
    </>
  );

  return page ? (
    <Flex align="stretch" direction="column" gap={8}>
      {rows}
    </Flex>
  ) : (
    rows
  );
};

export const ChargesSection = () => {
  const { access } = useCharges();

  if (access === "none") {
    return null;
  }

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Начисления</h2>
        </Typography.Text>

        <ChargesList />

        <ModelNote text="Начисления - модельные данные для демонстрации" />
      </section>
    </Flex>
  );
};
