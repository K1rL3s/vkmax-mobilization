import { flatsConfigs } from "./flats";
import { housesConfigs } from "./houses";
import { meConfigs } from "./me";
import { requestsConfigs } from "./requests";

export const mockConfigs = [
  ...meConfigs,
  ...housesConfigs,
  ...flatsConfigs,
  ...requestsConfigs,
];

export { resetState } from "./state";
