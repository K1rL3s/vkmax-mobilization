FROM ghcr.io/pnpm/pnpm:11 AS base
RUN pnpm_config_store_dir=/pnpm/runtime-store pnpm runtime set node 24 -g
COPY . /app
WORKDIR /app

FROM base AS build

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm i --frozen-lockfile --trust-lockfile
RUN pnpm build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
