import { useLocalStorage } from "@siberiacancode/reactuse";
import { z } from "zod";

const settingsSchema = z.object({
  basemap: z
    .enum(["auto", "light", "bright", "liberty", "dark", "fiord", "osm"])
    .catch("auto"),
  threeD: z.boolean().catch(false),
  cluster: z.boolean().catch(true),
  labels: z.boolean().catch(false),
  sizeByCount: z.boolean().catch(true),
});

export type MapSettings = z.infer<typeof settingsSchema>;

export const DEFAULT_MAP_SETTINGS = settingsSchema.parse({});

export const useMapSettings = () => {
  const stored = useLocalStorage<unknown>("zheka.map", DEFAULT_MAP_SETTINGS);
  const parsed = settingsSchema.safeParse(stored.value ?? {});
  const settings = parsed.success ? parsed.data : DEFAULT_MAP_SETTINGS;
  return [settings, (next: MapSettings) => stored.set(next)] as const;
};
