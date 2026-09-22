import { flatsConfigs } from "./flats";
import { housesConfigs } from "./houses";
import { meConfigs } from "./me";
import { metersConfigs } from "./meters";
import { pollsConfigs } from "./polls";
import { requestsConfigs } from "./requests";

export const mockConfigs = [
  ...meConfigs,
  ...housesConfigs,
  ...flatsConfigs,
  ...metersConfigs,
  ...requestsConfigs,
  ...pollsConfigs,
];

export { resetState } from "./state";
