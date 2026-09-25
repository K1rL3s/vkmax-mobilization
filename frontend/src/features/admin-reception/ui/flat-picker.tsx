import { Button, Flex, Input, Typography } from "@maxhub/max-ui";

import { useHouseResidents } from "@/features/admin-houses";
import { Checkbox } from "@/shared/ui/checkbox";
import { Icon, searchOutlineIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { eligibleFlats, type AccessFlat } from "../domain/access-form";

import styles from "./flat-picker.module.css";

type FlatPickerProps = {
  houseId: number;
  flatsCount: number;
  selected: AccessFlat[];
  onToggle: (flat: AccessFlat, checked: boolean) => void;
};

export const FlatPicker = ({
  houseId,
  flatsCount,
  selected,
  onToggle,
}: FlatPickerProps) => {
  const residents = useHouseResidents(houseId, 50);
  const flats = eligibleFlats(residents.items);

  const withoutResident =
    residents.isSearching || residents.hasMore ? 0 : flatsCount - flats.length;

  const list = () => {
    if (residents.isPending) {
      return <LoadingState title="Загружаем квартиры" />;
    }

    if (residents.isError) {
      return (
        <ErrorState
          description="Не получилось загрузить квартиры дома"
          onRetry={residents.retry}
        />
      );
    }

    if (flats.length === 0) {
      return residents.isSearching ? (
        <EmptyState
          title="Такой квартиры нет"
          description="Ищите по номеру квартиры или по имени жителя. Квартиры без подтверждённого жителя в списке не показываются"
        />
      ) : (
        <EmptyState
          title="Подтверждённых квартир нет"
          description="Ячейку в сборе получает только квартира с подтверждённым жителем: в этом доме таких пока нет"
        />
      );
    }

    return (
      <>
        <div className={styles.Cells}>
          {flats.map((flat) => {
            const checked = selected.some(
              (item) => item.flat_id === flat.flat_id,
            );

            return (
              <Checkbox
                key={flat.flat_id}
                className={styles.Row}
                checked={checked}
                onChange={(next) => onToggle(flat, next)}
              >
                <Flex align="stretch" direction="column" gapY={2}>
                  <Typography.Text variant="body" color="primary">
                    Кв. {flat.flat_number}
                  </Typography.Text>

                  <Typography.Text variant="description" color="secondary">
                    {flat.name}
                  </Typography.Text>
                </Flex>
              </Checkbox>
            );
          })}
        </div>

        {residents.hasMore && (
          <Flex align="center" gap={8} wrap="wrap">
            <Button
              type="button"
              size="small"
              variant="secondary"
              loading={residents.isLoadingMore}
              onClick={residents.loadMore}
            >
              Показать ещё
            </Button>

            <Typography.Text variant="detail" color="secondary">
              Загружено {residents.items.length} из {residents.total} жителей
            </Typography.Text>
          </Flex>
        )}

        {withoutResident > 0 && (
          <Typography.Text variant="detail" color="secondary">
            Ещё {withoutResident} квартир без подтверждённого жителя: им некому
            открыть
          </Typography.Text>
        )}
      </>
    );
  };

  return (
    <>
      {selected.length > 0 && (
        <div className={styles.Chips}>
          {selected.map((flat) => (
            <button
              key={flat.flat_id}
              type="button"
              className={styles.Chip}
              onClick={() => onToggle(flat, false)}
            >
              <Typography.Text variant="description" color="primary">
                кв. {flat.flat_number} ✕
              </Typography.Text>
            </button>
          ))}
        </div>
      )}

      <Input
        placeholder="Номер квартиры или имя жителя"
        maxLength={100}
        iconBefore={<Icon src={searchOutlineIcon} size={20} />}
        value={residents.query}
        onChange={(event) => residents.setQuery(event.target.value)}
      />

      {list()}
    </>
  );
};
