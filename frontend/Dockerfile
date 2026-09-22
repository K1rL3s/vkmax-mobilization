FROM ghcr.io/pnpm/pnpm:11.27.1@sha256:cc8a0551f7df20e46d6b089baf8f5f444fbd36de84ca72fd499171e474d8ec47 AS base
RUN pnpm_config_store_dir=/pnpm/runtime-store pnpm runtime set node 24.21.0 -g
COPY . /app
WORKDIR /app

FROM base AS build

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm i --frozen-lockfile --trust-lockfile
RUN pnpm build

FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
