import { Button, Typography } from "@maxhub/max-ui";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { PublicHouseMap } from "@/features/house-map";
import { errorMessage } from "@/shared/api/errors";
import { Autocomplete } from "@/shared/ui/autocomplete";
import { searchOutlineIcon } from "@/shared/ui/icon";
import { ErrorState } from "@/shared/ui/state";

import { useHouseSelect } from "./model/use-house-select";

import styles from "./house-select.module.css";

const viewSchema = z.enum(["map", "list"]).catch("map");

const HouseSelectPage = () => {
  const form = useHouseSelect();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = viewSchema.parse(searchParams.get("view") ?? undefined);

  const switchTo = (next: "map" | "list") =>
    setSearchParams(
      (previous) => {
        const params = new URLSearchParams(previous);
        if (next === "list") params.set("view", "list");
        else params.delete("view");
        return params;
      },
      { replace: true },
    );

  const views = (
    <>
      <div className={styles.Views}>
        {(
          [
            ["map", "На карте"],
            ["list", "Списком"],
          ] as const
        ).map(([id, label]) => (
          <Button
            key={id}
            size="small"
            variant={view === id ? "primary" : "secondary"}
            aria-pressed={view === id}
            onClick={() => switchTo(id)}
          >
            {label}
          </Button>
        ))}
      </div>
      <Typography.Text
        className={styles.Hint}
        variant="description"
        color="secondary"
      >
        Найдите свой дом и укажите номер квартиры
      </Typography.Text>
    </>
  );

  if (view === "map") {
    return (
      <div className={styles.Page}>
        {views}
        <PublicHouseMap
          onPick={(house) => {
            form.pickHouse(house);
            switchTo("list");
          }}
          onUnavailable={() => switchTo("list")}
        />
      </div>
    );
  }

  return (
    <div className={styles.Page}>
      {views}
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
          emptyDescription="Проверьте название улицы или найдите дом «На карте» - там его можно добавить"
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
          emptyDescription="Управляющая компания могла ещё не завести её в системе. Если номер верный, нажмите «Далее»"
        />

        {form.isAlreadyLinked && (
          <Typography.Text variant="description" color="secondary">
            Вы уже привязаны к этому дому. Выберите другой адрес.
          </Typography.Text>
        )}

        {form.linkError && (
          <ErrorState
            title="Не получилось добавить дом"
            description={errorMessage(
              form.linkError,
              "Проверьте связь и попробуйте ещё раз",
            )}
            error={form.linkError}
            onRetry={form.submit}
          />
        )}
      </div>

      <div className={styles.Footer}>
        {form.missing && (
          <Typography.Text
            className={styles.Missing}
            variant="description"
            color="secondary"
          >
            {form.missing}
          </Typography.Text>
        )}

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
