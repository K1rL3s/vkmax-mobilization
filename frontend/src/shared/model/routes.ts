export const Routes = {
  WELCOME: "/",
  PRIVACY: "/privacy",
  ONBOARDING_HOUSE: "/onboarding/house",
  FLAT_CONFIRMATION: "/residencies/:residentId/confirm",
  FLAT_CONFIRMATION_METHOD: "/residencies/:residentId/confirm/:method",
  HOME: "/home",
  REQUESTS: "/requests",
  MEETINGS: "/meetings",
  PROFILE: "/profile",
  OUTSIDE_MAX: "/outside-max",
} as const;
