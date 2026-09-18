import type { FlatMockServerConfig } from "mock-config-server";

import { mockConfigs } from "./src/shared/api/mocks";

const config: FlatMockServerConfig = [
  { baseUrl: "/api", port: 31299 },
  { configs: mockConfigs },
];

export default config;
