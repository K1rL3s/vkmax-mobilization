import { Button, Typography } from "@maxhub/max-ui";

import { Autocomplete } from "@/shared/ui/autocomplete";
import { searchOutlineIcon } from "@/shared/ui/icon";
import { ErrorState } from "@/shared/ui/state";

import { useHouseSelect } from "./model/use-house-select";

import styles from "./house-select.module.css";

const HouseSelectPage = () => {
  const form = useHouseSelect();

  const manualFlatAction = (
    <Typography.Text asChild variant="detail-strong">
      <button
        type="button"
        className={styles.TextButton}
        onClick={form.enableManualFlat}
      >
        Указать номер вручную
      </button>
    </Typography.Text>
  );

  return (
    <div className={styles.Page}>
      <div className={styles.Form}>
        <Autocomplete
          placeholder="Улица и номер дома"
          icon={searchOutlineIcon}
          value={form.query}
          onChange={form.changeQuery}
          options={form.houseOptions}
          onSelect={form.selectHouse}
          status={form.housesStatus}
          onRetry={form.retryHouses}
          loadingText="Ищем адреса…"
          emptyDescription="Проверьте название улицы или попробуйте ввести только её часть"
        />

        <Autocomplete
          placeholder="Номер квартиры"
          inputMode="numeric"
          disabled={form.isFlatDisabled}
          value={form.flatValue}
          onChange={form.changeFlatQuery}
          options={form.flatOptions}
          onSelect={form.selectFlat}
          status={form.flatsStatus}
          onRetry={form.retryFlats}
          loadingText="Ищем квартиру…"
          emptyTitle={form.emptyFlatTitle}
          emptyDescription="Управляющая компания могла ещё не завести её в системе"
          emptyAction={manualFlatAction}
        />

        {form.isAlreadyLinked && (
          <Typography.Text variant="description" color="secondary">
            Вы уже привязаны к этому дому. Выберите другой адрес.
          </Typography.Text>
        )}

        {form.isLinkFailed && (
          <ErrorState
            title="Не получилось добавить дом"
            description="Проверьте связь и попробуйте ещё раз"
            onRetry={form.submit}
          />
        )}
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          loading={form.isLinking}
          disabled={form.isSubmitDisabled}
          onClick={form.submit}
        >
          Далее
        </Button>
      </div>
    </div>
  );
};

export const Component = HouseSelectPage;
