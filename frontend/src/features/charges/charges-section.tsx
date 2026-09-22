import { Button, CellSimple, Flex, Typography } from "@maxhub/max-ui";
import { generatePath, Link, useNavigate } from "react-router-dom";

import { confirmationView } from "@/features/flat-confirmation";
import { Routes } from "@/shared/model/routes";
import { Icon, infoIcon, receiptIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import {
  formatMoney,
  formatPeriod,
  listDelta,
  type ChargeItem,
} from "./charge";
import { useCharges } from "./use-charges";

import styles from "./charges-section.module.css";

// на «Моей квартире» хватает последних месяцев, остальное - в истории
const SECTION_ROWS = 3;

export const ModelNote = ({ text }: { text: string }) => (
  <Flex align="center" gap={12} className={styles.Note}>
    <Icon src={infoIcon} size={24} className={styles.NoteIcon} />
    <Typography.Text variant="description" color="secondary">
      {text}
    </Typography.Text>
  </Flex>
);

export const ChargeRows = ({
  items,
  limit,
  more,
}: {
  items: ChargeItem[];
  limit?: number;
  more?: { count: number; onClick: () => void };
}) => {
  const navigate = useNavigate();

  return (
    <div className={styles.Panel}>
      {items.slice(0, limit).map((item, index) => {
        // соседний месяц берётся из полного списка: последней видимой строке
        // тоже есть с чем сравнить
        const delta = listDelta(item, items[index + 1]);

        return (
          <CellSimple
            key={item.id}
            separator={index > 0}
            title={formatPeriod(item.period)}
            subtitle={[delta, item.paid_at && "оплачено"]
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
        );
      })}

      {more && (
        <CellSimple
          separator
          title="Вся история"
          after={
            <Typography.Text
              variant="body"
              color="secondary"
              className={styles.Amount}
            >
              {more.count}
            </Typography.Text>
          }
          showChevron
          onClick={more.onClick}
        />
      )}
    </div>
  );
};

/**
 * Что показать вместо списка, когда начисления закрыты: арендатору - что так
 * задумано, неподтверждённому жителю - как открыть. `null` - список доступен
 */
export const ChargesGate = () => {
  const { residency, access } = useCharges();

  if (!residency || access === "open" || access === "none") {
    return null;
  }

  if (access === "tenant") {
    return (
      <EmptyState
        icon={receiptIcon}
        title="Начисления видит собственник"
        description="Арендатору они закрыты намеренно: квитанции, суммы и лицевой счёт остаются у владельца квартиры"
      />
    );
  }

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
};

export const ChargesSection = () => {
  const navigate = useNavigate();
  const { access, list } = useCharges();

  // без подключённого дома и квартиры в данных УК про начисления говорить
  // нечего: блок «О квартире» выше уже объясняет, чего не хватает
  if (access === "none") {
    return null;
  }

  const content = () => {
    if (access !== "open") {
      return <ChargesGate />;
    }

    if (list.isPending) {
      return <LoadingState title="Загружаем начисления" />;
    }

    if (list.isError) {
      return <ErrorState onRetry={() => void list.refetch()} />;
    }

    if (list.data.items.length === 0) {
      return (
        <EmptyState
          icon={receiptIcon}
          title="Начислений пока нет"
          description="Квитанция появится здесь, когда УК закроет первый месяц"
        />
      );
    }

    const { items, total } = list.data;

    return (
      <>
        <ChargeRows
          items={items}
          limit={SECTION_ROWS}
          more={
            total > SECTION_ROWS
              ? { count: total, onClick: () => void navigate(Routes.CHARGES) }
              : undefined
          }
        />
        <Typography.Text variant="description" color="secondary">
          Откройте месяц, чтобы увидеть, что изменилось: тариф или расход
        </Typography.Text>
      </>
    );
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Начисления</h2>
        </Typography.Text>

        {content()}

        <ModelNote text="Начисления - модельные данные для демонстрации" />
      </section>
    </Flex>
  );
};
