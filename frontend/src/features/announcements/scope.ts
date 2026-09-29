export const entrancesLabel = (entrances: number[]) =>
  `${entrances.length > 1 ? "Подъезды" : "Подъезд"} ${entrances.join(", ")}`;
