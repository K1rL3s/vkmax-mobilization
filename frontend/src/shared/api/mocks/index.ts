import { flatsConfigs } from "./flats";
import { housesConfigs } from "./houses";
import { meConfigs } from "./me";

export const mockConfigs = [...meConfigs, ...housesConfigs, ...flatsConfigs];

export { resetState } from "./state";
