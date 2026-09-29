import { type ReactNode, useEffect, useRef } from "react";
import { Button, CellSimple, Flex, Switch, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";

import { BASEMAPS } from "./basemaps";
import type { MapSettings } from "./map-settings";

import styles from "./settings-sheet.module.css";

export type MapSettingsSheetProps = {
  open: boolean;
  onClose: () => void;
  settings: MapSettings;
  onChange: (next: MapSettings) => void;
  sizeOption?: boolean;
  children?: ReactNode;
};

export const MapSettingsSheet = ({
  open,
  onClose,
  settings,
  onChange,
  sizeOption = false,
  children,
}: MapSettingsSheetProps) => {
  const dialog = useRef<HTMLDialogElement>(null);
  const raster = BASEMAPS.some(
    (basemap) => basemap.id === settings.basemap && basemap.kind === "raster",
  );
  const choices = [
    { id: "auto", label: "Как в MAX", swatch: ["#f4f3ef", "#1c1f24"] },
    ...BASEMAPS,
  ] as const;

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  const toggle = (
    key: "threeD" | "cluster" | "labels" | "sizeByCount",
    title: string,
    subtitle?: string,
  ) => (
    <CellSimple
      as="label"
      className={styles.Toggle}
      title={title}
      subtitle={subtitle}
      disabled={Boolean(subtitle)}
      after={
        <Switch
          checked={settings[key] && !subtitle}
          disabled={Boolean(subtitle)}
          onChange={(event) =>
            onChange({ ...settings, [key]: event.target.checked })
          }
        />
      }
    />
  );

  return (
    <dialog ref={dialog} className={styles.Sheet} onClose={onClose}>
      <Flex align="stretch" direction="column" gapY={12}>
        <Typography.Text asChild variant="title" color="primary">
          <h2 className={styles.Title}>Подложка</h2>
        </Typography.Text>

        <div className={styles.Basemaps}>
          {choices.map((choice) => (
            <button
              key={choice.id}
              type="button"
              aria-pressed={settings.basemap === choice.id}
              className={cn(
                styles.Basemap,
                settings.basemap === choice.id && styles.chosen,
              )}
              onClick={() => onChange({ ...settings, basemap: choice.id })}
            >
              <span
                className={styles.Swatch}
                style={{
                  background: `linear-gradient(135deg, ${choice.swatch[0]} 50%, ${choice.swatch[1]} 50%)`,
                }}
              />
              <Typography.Text variant="description" color="primary">
                {choice.label}
              </Typography.Text>
            </button>
          ))}
        </div>

        <Flex align="stretch" direction="column">
          {toggle(
            "threeD",
            "Объёмные здания",
            raster ? "Только на векторных подложках" : undefined,
          )}
          {toggle("cluster", "Группировать дома")}
          {toggle("labels", "Номера домов")}
          {sizeOption && toggle("sizeByCount", "Размер по числу заявок")}
        </Flex>

        {children && (
          <>
            <hr className={styles.Divider} />
            {children}
          </>
        )}

        <Button
          size="large"
          stretched
          variant="secondary"
          onClick={() => dialog.current?.close()}
        >
          Готово
        </Button>
      </Flex>
    </dialog>
  );
};
