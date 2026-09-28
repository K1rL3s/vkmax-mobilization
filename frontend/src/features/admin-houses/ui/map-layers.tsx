import type { ReactNode } from "react";
import {
  Button,
  CellSimple,
  Flex,
  Input,
  Radio,
  Switch,
  Typography,
} from "@maxhub/max-ui";

import { useRequestCategories } from "@/features/request";
import type { components } from "@/shared/api/schema/generated";
import { Checkbox } from "@/shared/ui/checkbox";
import { StatusPill } from "@/shared/ui/status-pill";

import { type AdminMapModel, PLATFORM_KINDS } from "../model/use-admin-map";

import styles from "./houses-map.module.css";

type MapOrg = components["schemas"]["MapOrg"];

const Group = ({ title, children }: { title: string; children: ReactNode }) => (
  <Flex asChild align="stretch" direction="column" gapY={8}>
    <section>
      <Typography.Text asChild variant="title" color="primary">
        <h3 className={styles.GroupTitle}>{title}</h3>
      </Typography.Text>
      {children}
    </section>
  </Flex>
);

const Chips = <T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) => (
  <div className={styles.SheetChips} role="radiogroup" aria-label={label}>
    {options.map((option) => (
      <Button
        key={option.id}
        type="button"
        role="radio"
        aria-checked={option.id === value}
        size="small"
        variant={option.id === value ? "primary" : "secondary"}
        onClick={() => onChange(option.id)}
      >
        {option.label}
      </Button>
    ))}
  </div>
);

const RANGE = /^(\d*)-(\d*)$/;

export const MapLayers = ({
  map,
  orgs,
}: {
  map: AdminMapModel;
  orgs: MapOrg[];
}) => {
  const { filters, update, toggle, isAdmin } = map;
  const categories = useRequestCategories();

  const rangeParts = (name: "ontime" | "rating") =>
    RANGE.exec(filters[name] ?? "")?.slice(1) ?? ["", ""];

  const setRange = (
    name: "ontime" | "rating",
    side: 0 | 1,
    raw: string,
    scale: number,
  ) => {
    const value = Number(raw.replace(",", "."));
    const parts = rangeParts(name);
    parts[side] =
      raw.trim() === "" || !Number.isFinite(value) || value < 0
        ? ""
        : String(Math.round(value * scale));
    const next = parts.join("-");
    update({ [name]: next === "-" ? null : next });
  };

  const range = (
    name: "ontime" | "rating",
    title: string,
    scale: number,
    hint: string,
  ) => {
    const parts = rangeParts(name);
    return (
      <Group title={title}>
        <div className={styles.Range}>
          {(["от", "до"] as const).map((placeholder, side) => (
            <Input
              key={placeholder}
              aria-label={`${title}: ${placeholder}`}
              placeholder={placeholder}
              inputMode={scale === 1 ? "numeric" : "decimal"}
              maxLength={4}
              defaultValue={
                parts[side] === ""
                  ? ""
                  : String(Number(parts[side]) / scale).replace(".", ",")
              }
              onChange={(event) =>
                setRange(name, side as 0 | 1, event.target.value, scale)
              }
            />
          ))}
        </div>
        <Typography.Text variant="description" color="secondary">
          {hint}
        </Typography.Text>
      </Group>
    );
  };

  return (
    <Flex align="stretch" direction="column" gapY={20}>
      <Group title="Цвет домов">
        <div>
          {[
            { id: "requests", title: "Заявки", subtitle: "Самое тревожное" },
            {
              id: "meters",
              title: "Счётчики",
              subtitle: "Доля квартир, подавших показания",
            },
            ...(isAdmin
              ? [
                  {
                    id: "residents",
                    title: "Жители",
                    subtitle: "Доля квартир с жителями в MAX",
                  },
                ]
              : []),
          ].map((mode) => (
            <CellSimple
              key={mode.id}
              as="label"
              className={styles.SheetCell}
              title={mode.title}
              subtitle={mode.subtitle}
              after={
                <Radio
                  name="map-color"
                  checked={filters.color === mode.id}
                  onChange={() =>
                    update({ color: mode.id === "requests" ? null : mode.id })
                  }
                />
              }
            />
          ))}
        </div>
      </Group>

      <div>
        <CellSimple
          as="label"
          className={styles.SheetCell}
          title="Тепловая карта"
          subtitle="Где больше заявок за период"
          after={
            <Switch
              checked={filters.heat}
              onChange={(event) =>
                update({ heat: event.target.checked ? "1" : null })
              }
            />
          }
        />
        <CellSimple
          as="label"
          className={styles.SheetCell}
          title="Вся платформа"
          subtitle="Дома других УК и дома без УК"
          after={
            <Switch
              checked={filters.platform}
              onChange={(event) =>
                update({ platform: event.target.checked ? "1" : null })
              }
            />
          }
        />
      </div>

      <Group title="Категория заявок">
        <Chips
          label="Категория заявок"
          options={[
            { id: "all", label: "Все" },
            ...(categories.data ?? []).map(({ category, label }) => ({
              id: category,
              label,
            })),
          ]}
          value={filters.category ?? "all"}
          onChange={(id) => update({ category: id === "all" ? null : id })}
        />
      </Group>

      <Group title="Период">
        <Chips
          label="Период"
          options={[
            { id: "week", label: "Неделя" },
            { id: "month", label: "Месяц" },
            { id: "quarter", label: "Квартал" },
            { id: "half", label: "Полгода" },
          ]}
          value={filters.period}
          onChange={(id) => update({ period: id === "month" ? null : id })}
        />
        <Typography.Text variant="description" color="secondary">
          Для тепловой карты и оценки жителей
        </Typography.Text>
      </Group>

      {filters.platform && (
        <>
          <Group title="Дома на платформе">
            <div>
              {PLATFORM_KINDS.map((kind) => (
                <Checkbox
                  key={kind.id}
                  className={styles.Check}
                  checked={filters.pkind.includes(kind.id)}
                  onChange={() => toggle("pkind", kind.id)}
                >
                  {kind.label}
                </Checkbox>
              ))}
              <Checkbox
                className={styles.Check}
                checked={filters.pwait}
                onChange={(checked) => update({ pwait: checked ? "1" : null })}
              >
                Ждут УК: жители просят подключить свою УК
              </Checkbox>
            </div>
          </Group>

          {orgs.length > 0 && (
            <Group title="УК в этой части карты">
              <div>
                {orgs.map((org) => (
                  <Checkbox
                    key={org.id}
                    className={styles.Check}
                    checked={filters.porg.includes(org.id)}
                    onChange={() => toggle("porg", org.id)}
                  >
                    <Flex align="center" gap={6} wrap="wrap">
                      {org.name}
                      {org.is_demo && (
                        <StatusPill tone="themed">демо</StatusPill>
                      )}
                    </Flex>
                  </Checkbox>
                ))}
              </div>
            </Group>
          )}

          {range(
            "ontime",
            "В срок, %",
            1,
            "Доля заявок УК, сделанных в срок за 90 дней",
          )}
          {range("rating", "Оценка", 10, "Средняя оценка УК от 1 до 5")}
        </>
      )}
    </Flex>
  );
};
