/** PM2: раздача статики из web/out через serve на порту 3000. Nginx проксирует сюда. */
const path = require("path");

module.exports = {
  apps: [
    {
      name: "music-exile",
      cwd: __dirname,
      script: path.join(__dirname, "node_modules/serve/build/main.js"),
      args: "out -l 3000 --no-clipboard",
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "200M",
      env: {
        NODE_ENV: "production",
      },
    },
  ],
};
