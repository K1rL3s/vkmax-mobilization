import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { App } from "./app";
import { Providers } from "./providers";
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
    ],
  },
]);

export const Router = () => {
  return <RouterProvider router={router} />;
};
