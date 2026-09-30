import type { components } from "@/shared/api/schema/generated";

export type House = Pick<
  components["schemas"]["HouseListItem"],
  "id" | "address"
>;

export type Flat = components["schemas"]["FlatListItem"];
