import { getMaxLaunch, type MaxLaunch, type MaxUser } from "./launch";

export const useMaxLaunch = (): MaxLaunch => getMaxLaunch();

export const useMaxUser = (): MaxUser | null => getMaxLaunch().user;
