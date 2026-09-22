import { Button, Flex, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { homeIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import {
  calendarDay,
  dayTitle,
  type AccessRequest,
  type Schedule,
} from "../domain/schedule";

import styles from "./access-request-card.module.css";

type AccessRequestCardProps = {
  request: AccessRequest;
  schedule: Schedule;
  confirmPath: string | null;
  isPicking: boolean;
  pendingSlotId: number | undefined;
  error: string | null;
  onPick: (slotId: number) => void;
};

export const AccessRequestCard = ({
  request,
  schedule,
  confirmPath,
  isPicking,
  pendingSlotId,
  error,
  onPick,
}: AccessRequestCardProps) => {
  const mine = request.slots.find((slot) => slot.id === request.my_slot_id);

  return (
    <Flex direction="column" align="stretch" gap={12} className={styles.Card}>
      <Flex align="center" gap={12}>
        <IconTile icon={homeIcon} tone="promo" />
        <Flex
          direction="column"
          align="stretch"
          gapY={2}
          className={styles.Grow}
        >
          <Typography.Text variant="body-strong" color="primary">
            УК просит доступ в квартиру
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            {dayTitle(calendarDay(request.date))}
          </Typography.Text>
        </Flex>
      </Flex>

      <Typography.Text variant="detail" color="primary">
        {request.reason}
      </Typography.Text>

      {confirmPath ? (
        <Flex direction="column" align="stretch" gap={8}>
          <Typography.Text variant="description" color="secondary">
            Выбрать время может только подтверждённый житель квартиры.
            Подтверждение занимает пару минут
          </Typography.Text>
          <Button asChild size="medium" variant="secondary">
            <Link to={confirmPath}>Подтвердить квартиру</Link>
          </Button>
        </Flex>
      ) : (
        <>
          <div className={styles.Grid}>
            {request.slots.map((slot) => {
              const isMine = slot.id === request.my_slot_id;

              return (
                <Button
                  key={slot.id}
                  size="medium"
                  className={styles.Slot}
                  variant={isMine ? "primary" : "secondary"}
                  disabled={
                    isPicking || (!isMine && slot.taken >= slot.capacity)
                  }
                  loading={slot.id === pendingSlotId}
                  aria-pressed={isMine}
                  onClick={() => onPick(slot.id)}
                >
                  с {schedule.slotTime(slot.starts_at)}
                </Button>
              );
            })}
          </div>

          <Typography.Text variant="description" color="tertiary">
            {mine
              ? `Ждём вас с ${schedule.slotTime(mine.starts_at)}. Поменять время можно, пока в окне есть места`
              : "Выберите, когда вы будете дома. Бледные окна уже заполнены"}
          </Typography.Text>
        </>
      )}

      {error && (
        <Typography.Text variant="description" className={styles.Error}>
          {error}
        </Typography.Text>
      )}
    </Flex>
  );
};
