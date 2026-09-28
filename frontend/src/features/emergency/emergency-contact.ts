import type { HouseCard } from "@/features/house";

export type EmergencyContact = {
  phone: string;
  label: string;
  short: string;
  isEmergencyLine: boolean;
};

export const emergencyContact = (
  org: HouseCard["org"],
): EmergencyContact | null => {
  if (org?.emergency_phone) {
    return {
      phone: org.emergency_phone,
      label: "Аварийная служба дома",
      short: "АДС",
      isEmergencyLine: true,
    };
  }

  if (org?.phone.trim()) {
    return {
      phone: org.phone,
      label: "Телефон УК",
      short: "УК",
      isEmergencyLine: false,
    };
  }

  return null;
};
