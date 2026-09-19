#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

for (const file of [".env.local", ".env"]) {
  try {
    process.loadEnvFile(fileURLToPath(new URL(`../${file}`, import.meta.url)));
  } catch {
    //...
  }
}

const { values } = parseArgs({
  options: {
    host: { type: "string" },
    user: { type: "string" },
    identity: { type: "string", short: "i" },
    "local-port": { type: "string" },
    "local-host": { type: "string" },
    "remote-port": { type: "string" },
    "remote-bind": { type: "string" },
    "alive-interval": { type: "string" },
    "alive-count": { type: "string" },
    "dry-run": { type: "boolean", default: false },
    help: { type: "boolean", short: "h", default: false },
  },
});

if (values.help) {
  console.log(`Проброс локального dev-сервера на удалённый хост (reverse SSH tunnel).

Использование:
  pnpm tunnel [опции]

Значения берутся из флага, иначе из .env.local / .env, иначе из умолчания.
Скопируйте .env.local.example в .env.local и заполните переменные DEV_TUNNEL_*.

Опции:
  --host <host>             SSH-хост сервера            [DEV_TUNNEL_SSH_HOST]
  --user <user>             SSH-пользователь            [DEV_TUNNEL_SSH_USER]
  -i, --identity <path>     приватный ключ для ssh -i   [DEV_TUNNEL_SSH_KEY]
                            без него ssh берёт свои умолчания и агента
  --local-port <port>       порт локального dev-сервера [DEV_TUNNEL_LOCAL_PORT] (5173)
  --local-host <host>       хост локального dev-сервера [DEV_TUNNEL_LOCAL_HOST] (localhost)
  --remote-port <port>      порт на сервере             [DEV_TUNNEL_REMOTE_PORT] (5022)
  --remote-bind <addr>      адрес привязки на сервере   [DEV_TUNNEL_REMOTE_BIND] (127.0.0.1)
  --alive-interval <sec>    ServerAliveInterval (30)
  --alive-count <n>         ServerAliveCountMax (3)
  --dry-run                 показать команду ssh и выйти
  -h, --help                показать эту справку
`);
  process.exit(0);
}

const fail = (message: string): never => {
  console.error(message);
  process.exit(1);
};

type Option =
  | "host"
  | "user"
  | "local-port"
  | "local-host"
  | "remote-port"
  | "remote-bind"
  | "alive-interval"
  | "alive-count";

// флаг > переменная окружения (шелл или .env*) > умолчание
const setting = (
  option: Option,
  envName: string,
  fallback?: string,
): string => {
  const value = values[option] ?? process.env[envName] ?? fallback;
  if (typeof value !== "string" || value === "") {
    return fail(
      `Не задан --${option}: укажите ${envName} в .env.local (см. .env.local.example) или передайте --${option}.`,
    );
  }
  return value;
};

const port = (value: string, source: string): string => {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return fail(`Некорректный порт (${source}): ${value}`);
  }
  return String(parsed);
};

const host = setting("host", "DEV_TUNNEL_SSH_HOST");
const user = setting("user", "DEV_TUNNEL_SSH_USER");
const localHost = setting("local-host", "DEV_TUNNEL_LOCAL_HOST", "localhost");
const remoteBind = setting(
  "remote-bind",
  "DEV_TUNNEL_REMOTE_BIND",
  "127.0.0.1",
);
const localPort = port(
  setting("local-port", "DEV_TUNNEL_LOCAL_PORT", "5173"),
  "--local-port",
);
const remotePort = port(
  setting("remote-port", "DEV_TUNNEL_REMOTE_PORT", "5022"),
  "--remote-port",
);
const aliveInterval = setting(
  "alive-interval",
  "DEV_TUNNEL_ALIVE_INTERVAL",
  "30",
);
const aliveCount = setting("alive-count", "DEV_TUNNEL_ALIVE_COUNT", "3");

// ключ необязателен: без него ssh ищет его сам - по ~/.ssh/config и агенту
const identity = (): string | null => {
  const value = values.identity ?? process.env.DEV_TUNNEL_SSH_KEY ?? "";
  if (value === "") {
    return null;
  }
  // тильду раскрываем сами: ssh запускается без шелла, и в --dry-run должен
  // печататься тот же путь, по которому пойдёт соединение
  const path = value.startsWith("~/")
    ? resolve(homedir(), value.slice(2))
    : value;
  if (!existsSync(path)) {
    return fail(
      `Ключ не найден: ${path}. Проверьте DEV_TUNNEL_SSH_KEY в .env.local или --identity.`,
    );
  }
  return path;
};

const key = identity();

const args = [
  "-N",
  ...(key === null ? [] : ["-i", key]),
  "-R",
  `${remoteBind}:${remotePort}:${localHost}:${localPort}`,
  "-o",
  `ServerAliveInterval=${aliveInterval}`,
  "-o",
  `ServerAliveCountMax=${aliveCount}`,
  "-o",
  "ExitOnForwardFailure=yes",
  `${user}@${host}`,
];

if (values["dry-run"]) {
  console.log(["ssh", ...args].join(" "));
  process.exit(0);
}

console.log(
  `Туннель: ${host}:${remotePort} -> ${localHost}:${localPort} (Ctrl+C для остановки)`,
);

const ssh = spawn("ssh", args, { stdio: "inherit" });

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => ssh.kill(signal));
}

ssh.on("error", (error) => {
  console.error(`Не удалось запустить ssh: ${error.message}`);
  process.exit(1);
});

ssh.on("exit", (code, signal) => {
  process.exit(signal ? 1 : (code ?? 0));
});
