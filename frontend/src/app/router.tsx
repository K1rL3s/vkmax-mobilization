import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { App } from "./app";
import { Providers } from "./providers";
import { TabBarLayout } from "./layouts/tab-bar-layout";
import { Routes } from "@/shared/model/routes";

const router = createBrowserRouter([
  {
    element: (
      <Providers>
        <App />
      </Providers>
    ),
    children: [
      {
        path: Routes.ONBOARDING,
        lazy: () =>
          import("@/features/onboarding/onboarding-page/onboarding.page"),
      },
      {
        path: Routes.ONBOARDING_HOUSE,
        lazy: () =>
          import("@/features/onboarding/house-select-page/house-select.page"),
      },
      {
        element: <TabBarLayout />,
        children: [
          {
            path: Routes.HOME,
            lazy: () => import("@/features/home/home-page/home.page"),
          },
        ],
      },
    ],
  },
]);

export const Router = () => {
  return <RouterProvider router={router} />;
};
