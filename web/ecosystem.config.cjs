/** PM2: раздача статики из web/out через serve. Nginx проксирует на LISTEN_PORT. */
const path = require("path");

const LISTEN_PORT = 3010;

module.exports = {
  apps: [
    {
      name: "music-exile",
      cwd: __dirname,
      script: path.join(__dirname, "node_modules/serve/build/main.js"),
      args: `out -l tcp://127.0.0.1:${LISTEN_PORT} --no-clipboard`,
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "200M",
      env: {
        NODE_ENV: "production",
        PORT: LISTEN_PORT,
      },
    },
  ],
};
