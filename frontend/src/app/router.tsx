import { createBrowserRouter, Outlet, RouterProvider } from "react-router-dom";
import { App } from "./app";
import { Providers } from "./providers";
import { TabBar } from "@/features/tab-bar";
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
          import("@/features/onboarding/onboarding.page"),
      },
      {
        path: Routes.ONBOARDING_HOUSE,
        lazy: () =>
          import("@/features/onboarding/house-select.page"),
      },
      {
        element: (
          <>
            <Outlet />
            <TabBar />
          </>
        ),
        children: [
          {
            path: Routes.HOME,
            lazy: () => import("@/features/home/home.page"),
          },
        ],
      },
    ],
  },
]);

export const Router = () => {
  return <RouterProvider router={router} />;
};
