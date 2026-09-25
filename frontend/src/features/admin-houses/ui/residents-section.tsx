import { Button, Flex, Input, Tappable, Typography } from "@maxhub/max-ui";

import { Chevron } from "@/shared/ui/chevron";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { Icon, searchOutlineIcon, usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { type Resident, residentPlace } from "../domain/resident";
import { useHouseResidents } from "../model/use-house-residents";
import { useResidentActions } from "../model/use-resident-actions";
import { ReasonDialog } from "./reason-dialog";
import { ResidentSheet } from "./resident-sheet";

import styles from "./residents-section.module.css";

const ResidentRow = ({
  resident,
  onOpen,
}: {
  resident: Resident;
  onOpen: () => void;
}) => (
  <Tappable className={styles.Row} onClick={onOpen}>
    <Flex className={styles.Grow} align="stretch" direction="column" gapY={4}>
      <Typography.Text
        className={styles.Ellipsis}
        variant="body-strong"
        color="primary"
      >
        {resident.name}
      </Typography.Text>

      <Typography.Text variant="description" color="secondary">
        {residentPlace(resident)}
      </Typography.Text>

      <Flex align="center" gap={6} wrap="wrap">
        {resident.is_chairman && (
          <StatusPill tone="promo">Председатель</StatusPill>
        )}

        {resident.status === "blocked" && (
          <StatusPill tone="negative">Заблокирован</StatusPill>
        )}

        {resident.verified ? (
          <StatusPill tone="positive">Квартира подтверждена</StatusPill>
        ) : (
          <StatusPill tone="neutral">Не подтверждена</StatusPill>
        )}
      </Flex>

      {resident.status === "blocked" && resident.block_reason && (
        <Typography.Text variant="description" color="secondary">
          Причина: {resident.block_reason}
        </Typography.Text>
      )}
    </Flex>

    <Chevron />
  </Tappable>
);

const who = (resident: Resident) =>
  resident.flat_number
    ? `${resident.name}, кв. ${resident.flat_number}`
    : resident.name;

type ResidentsSectionProps = {
  houseId: number;
  chairmanName: string | null;
};

export const ResidentsSection = ({
  houseId,
  chairmanName,
}: ResidentsSectionProps) => {
  const residents = useHouseResidents(houseId);
  const actions = useResidentActions();
  const { resident, step } = actions;

  const content = () => {
    if (residents.isPending) {
      return <LoadingState title="Загружаем жителей" />;
    }

    if (residents.isError) {
      return (
        <ErrorState
          description="Не получилось загрузить жителей. Проверьте связь и попробуйте ещё раз"
          onRetry={residents.retry}
        />
      );
    }

    if (residents.items.length === 0) {
      return residents.isSearching ? (
        <EmptyState
          icon={usersIcon}
          title="Никого не нашли"
          description="Ищите по имени жителя или по номеру квартиры"
        />
      ) : (
        <EmptyState
          icon={usersIcon}
          title="Жителей пока нет"
          description="Жители появляются здесь, когда привязывают квартиру в боте или мини-приложении: например, по подъездному QR-коду"
        />
      );
    }

    return (
      <>
        {residents.items.map((item) => (
          <ResidentRow
            key={item.resident_id}
            resident={item}
            onOpen={() => actions.open(item)}
          />
        ))}

        {residents.hasMore && (
          <Button
            size="medium"
            variant="secondary"
            loading={residents.isLoadingMore}
            onClick={residents.loadMore}
          >
            Показать ещё
          </Button>
        )}
      </>
    );
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Flex align="baseline" gap={8}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.Title}>Жители</h2>
          </Typography.Text>

          {residents.total > 0 && !residents.isSearching && (
            <Typography.Text variant="body" color="secondary">
              {residents.total}
            </Typography.Text>
          )}
        </Flex>

        {(residents.total >= 10 || residents.query !== "") && (
          <Input
            placeholder="Имя или номер квартиры"
            maxLength={100}
            iconBefore={<Icon src={searchOutlineIcon} size={20} />}
            value={residents.query}
            onChange={(event) => residents.setQuery(event.target.value)}
          />
        )}

        {content()}

        {resident && step === "menu" && (
          <ResidentSheet
            resident={resident}
            isPending={actions.isPending}
            error={actions.error}
            onChoose={actions.choose}
            onClose={actions.close}
          />
        )}

        {resident && step === "block" && (
          <ReasonDialog
            title="Заблокировать в доме"
            description={`${who(resident)}. Житель потеряет доступ к дому в сервисе, а причину получит сообщением от бота вместе с контактами УК.`}
            presets={[
              {
                label: "Не живёт в доме",
                text: "Не проживает в доме и не является собственником квартиры",
              },
              {
                label: "Съехал",
                text: "Съехал из дома, квартира продана или сдана другим людям",
              },
              {
                label: "Нарушал правила",
                text: "Нарушал правила общения в чате дома после предупреждений",
              },
            ]}
            placeholder="За что житель заблокирован"
            submitLabel="Заблокировать"
            isPending={actions.isPending}
            error={actions.error}
            onSubmit={actions.submitReason}
            onClose={actions.close}
          />
        )}

        {resident && step === "revoke" && (
          <ReasonDialog
            title="Отозвать подтверждение"
            description={`${who(resident)}. Квартира станет неподтверждённой, пока житель не подтвердит её заново. Причину он получит сообщением от бота вместе с контактами УК.`}
            presets={[
              {
                label: "Сменился собственник",
                text: "Сменился собственник квартиры",
              },
              {
                label: "Ошибка сверки",
                text: "Квартира подтверждена по ошибке: лицевой счёт не совпадает с данными УК",
              },
              {
                label: "Кончился наём",
                text: "Закончился договор найма квартиры",
              },
            ]}
            placeholder="Почему подтверждение отозвано"
            submitLabel="Отозвать подтверждение"
            isPending={actions.isPending}
            error={actions.error}
            onSubmit={actions.submitReason}
            onClose={actions.close}
          />
        )}

        <ConfirmDialog
          isOpen={
            resident !== null && (step === "chairman" || step === "unchairman")
          }
          title={
            step === "unchairman"
              ? "Снять с должности председателя?"
              : "Назначить председателем?"
          }
          description={
            resident &&
            (step === "unchairman"
              ? `${resident.name} перестанет быть председателем совета дома: не сможет привязывать чат дома и закреплять в нём сообщения.`
              : `${resident.name} станет председателем совета дома: сможет привязать чат дома к сервису и закреплять в нём сообщения. Заблокировать председателя нельзя.${chairmanName ? ` Сейчас председатель - ${chairmanName}, он перестанет им быть.` : ""}`)
          }
          confirmLabel={
            step === "unchairman" ? "Снять с должности" : "Назначить"
          }
          isPending={actions.isPending}
          error={actions.error}
          onConfirm={actions.confirmChairman}
          onClose={actions.close}
        />
      </section>
    </Flex>
  );
};
