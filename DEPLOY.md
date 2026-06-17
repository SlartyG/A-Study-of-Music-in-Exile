# Деплой лонгрида на VPS

Пошаговая инструкция: от `git clone` до сайта на своём домене с HTTPS.

Схема: **Next.js static export** → папка `web/out/` → **PM2 + serve** на `:3010` → **nginx** reverse proxy → домен + SSL.

Замените `example.com` на свой домен везде, где встречается.

---

## 0. Что должно быть готово

| Что | Пример |
|-----|--------|
| VPS | Ubuntu 22.04 / 24.04, 1 GB RAM, публичный IPv4 |
| Домен | `example.com` |
| SSH-доступ | `ssh root@123.45.67.89` |
| DNS у регистратора | A-запись `@` → IP VPS |
| (опционально) | A-запись `www` → тот же IP |

Проверка DNS (с Mac, после сохранения записей, подождите 5–30 мин):

```bash
dig +short example.com
# должен вернуть IP вашего VPS
```

---

## 1. Подготовка VPS

Подключитесь по SSH:

```bash
ssh root@ВАШ_IP
```

Обновите систему и поставьте базовые пакеты:

```bash
apt update && apt upgrade -y
apt install -y git nginx certbot python3-certbot-nginx ufw curl
```

Файрвол:

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

Node.js 20 и PM2:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g pm2
node -v   # v20.x
pm2 -v
```

Автозапуск PM2 после перезагрузки сервера (выполнить один раз, скопировать и выполнить команду, которую выведет pm2):

```bash
pm2 startup systemd
# pm2 выведет строку вида: sudo env PATH=... pm2 startup ...
# выполните её, затем:
pm2 save
```

---

## 2. Клонирование, сборка, PM2

```bash
mkdir -p /var/www
cd /var/www
git clone https://github.com/SlartyG/A-Study-of-Music-in-Exile.git
cd A-Study-of-Music-in-Exile/web
npm ci
npm run build
pm2 start ecosystem.config.cjs
pm2 save
```

Проверка, что процесс живой:

```bash
pm2 status
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3010/
# ожидается 200
```

### Домен в метаданных (OG-теги)

Перед первой prod-сборкой замените `example.com` в `web/app/layout.tsx`:

```ts
metadataBase: new URL("https://example.com"),
```

Потом пересоберите: `npm run build && pm2 reload ecosystem.config.cjs`.

### Если пересобираете данные с нуля

```bash
cd /var/www/A-Study-of-Music-in-Exile
python3 analysis/export_for_web.py
cd web && npm run build && pm2 reload ecosystem.config.cjs
```

---

## 3. Nginx (reverse proxy → PM2)

Создайте конфиг:

```bash
nano /etc/nginx/sites-available/music-exile
```

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;

    gzip on;
    gzip_vary on;
    gzip_min_length 256;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/javascript
        application/json
        image/svg+xml;

    location /_next/static/ {
        proxy_pass http://127.0.0.1:3010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:3010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите сайт:

```bash
ln -s /etc/nginx/sites-available/music-exile /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Откройте `http://example.com` — лонгрид должен открыться.

---

## 4. HTTPS (Let's Encrypt)

```bash
certbot --nginx -d example.com -d www.example.com
```

Проверка продления:

```bash
certbot renew --dry-run
```

---

## 5. Обновление (деплой из git)

На VPS из корня репозитория:

```bash
cd /var/www/A-Study-of-Music-in-Exile
./scripts/deploy.sh
```

Скрипт делает: `git pull` → `npm ci` → `npm run build` → `pm2 reload` (или `pm2 start` при первом запуске).

Вручную, без скрипта:

```bash
cd /var/www/A-Study-of-Music-in-Exile/web
git pull
npm ci
npm run deploy    # build + pm2 reload
```

### PM2: полезные команды

```bash
pm2 status              # статус
pm2 logs music-exile    # логи
pm2 restart music-exile # жёсткий рестарт
pm2 monit               # мониторинг CPU/RAM
```

Файл конфигурации: `web/ecosystem.config.cjs`.

---

## 6. Альтернатива: сборка на Mac, заливка на сервер

Если на VPS мало RAM и `npm run build` падает:

```bash
# На Mac
cd web
npm ci && npm run build
rsync -avz --delete out/ root@ВАШ_IP:/var/www/A-Study-of-Music-in-Exile/web/out/

# На VPS — только перезапуск PM2 (файлы уже на месте)
ssh root@ВАШ_IP "pm2 reload music-exile"
```

---

## 7. Частые проблемы

| Симптом | Решение |
|---------|---------|
| `dig` не показывает IP VPS | Подождать TTL DNS или проверить A-запись |
| Certbot: failed to verify | DNS не обновился; порт 80 закрыт |
| 502 Bad Gateway | PM2 не запущен: `pm2 start web/ecosystem.config.cjs` |
| Сайт не поднялся после reboot | `pm2 startup` + `pm2 save` |
| `npm run build` OOM | Собрать на Mac + rsync (раздел 6) |
| Порт 3010 занят | В `ecosystem.config.cjs` сменить `LISTEN_PORT` и nginx `proxy_pass` |

---

## 8. Чеклист перед публикацией

- [ ] DNS A-запись указывает на VPS
- [ ] `metadataBase` в `web/app/layout.tsx` = ваш домен
- [ ] `npm run build` проходит без ошибок
- [ ] `pm2 status` — `music-exile` online
- [ ] `curl localhost:3010` → 200
- [ ] Сайт открывается по HTTPS
- [ ] `pm2 startup` настроен

---

Автор: Веселов Александр
