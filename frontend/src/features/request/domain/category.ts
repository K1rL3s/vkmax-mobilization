import {
  bulbIcon,
  buildingIcon,
  dropletIcon,
  elevatorIcon,
  flameIcon,
  meterIcon,
  receiptIcon,
  trashIcon,
  treeIcon,
  wrenchIcon,
} from "@/shared/ui/icon";

import type { RequestCategory, ResponsibilityZone } from "./types";

export const CATEGORY_ICON: Record<RequestCategory, string> = {
  leak: dropletIcon,
  water_supply: dropletIcon,
  heating: flameIcon,
  electricity: bulbIcon,
  elevator: elevatorIcon,
  garbage: trashIcon,
  entrance: buildingIcon,
  yard: treeIcon,
  meter_error: meterIcon,
  charge_dispute: receiptIcon,
  other: wrenchIcon,
};

export const ZONE_LABEL: Record<ResponsibilityZone, string> = {
  management: "Управляющая компания",
  utility: "Ресурсоснабжающая организация",
  municipality: "Муниципалитет",
};

export const NO_NORM = "Срок сервиса, норматива нет";
