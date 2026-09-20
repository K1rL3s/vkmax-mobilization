import { flatsConfigs } from "./flats";
import { housesConfigs } from "./houses";
import { meConfigs } from "./me";
import { metersConfigs } from "./meters";
import { requestsConfigs } from "./requests";

export const mockConfigs = [
  ...meConfigs,
  ...housesConfigs,
  ...flatsConfigs,
  ...metersConfigs,
  ...requestsConfigs,
];

export { resetState } from "./state";
