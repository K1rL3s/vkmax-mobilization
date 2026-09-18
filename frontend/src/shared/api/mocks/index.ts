import { housesConfigs } from "./houses";
import { meConfigs } from "./me";

export const mockConfigs = [...meConfigs, ...housesConfigs];

export { resetState } from "./state";
