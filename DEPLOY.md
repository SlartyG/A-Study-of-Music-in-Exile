# Деплой лонгрида на VPS

Пошаговая инструкция: от `git clone` до сайта на своём домене с HTTPS.

Сайт — статический экспорт Next.js (`web/out/`). На сервере в рантайме Node.js не нужен, только для сборки.

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

Node.js 20 (для сборки):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
node -v   # v20.x
npm -v
```

---

## 2. Клонирование и сборка

```bash
mkdir -p /var/www
cd /var/www
git clone https://github.com/SlartyG/A-Study-of-Music-in-Exile.git
cd A-Study-of-Music-in-Exile/web
npm ci
npm run build
```

После сборки статика лежит в `/var/www/A-Study-of-Music-in-Exile/web/out/`.

Проверка без домена (на VPS):

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/
# пока nginx не настроен — 404 или дефолтная страница nginx, это нормально
```

### Домен в метаданных (OG-теги)

Перед сборкой на проде замените `example.com` в `web/app/layout.tsx`:

```ts
metadataBase: new URL("https://example.com"),
```

Или соберите локально с правильным доменом и залейте `out/` через `rsync` (см. раздел «Обновление»).

### Если пересобираете данные с нуля

На машине с Python и CSV-результатами анализа:

```bash
cd /var/www/A-Study-of-Music-in-Exile
python3 analysis/export_for_web.py
cd web && npm run build
```

Для деплоя уже готового лонгрида этот шаг не обязателен: JSON и картинки уже в репозитории.

---

## 3. Nginx

Создайте конфиг:

```bash
nano /etc/nginx/sites-available/music-exile
```

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;

    root /var/www/A-Study-of-Music-in-Exile/web/out;
    index index.html;

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

    # Долгий кэш для хэшированных чанков Next.js
    location /_next/static/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # Картинки и JSON
    location /images/ {
        add_header Cache-Control "public, max-age=86400";
    }
    location /data/ {
        add_header Cache-Control "public, max-age=3600";
    }

    # Статический экспорт Next.js (trailingSlash: true)
    location / {
        try_files $uri $uri/ $uri/index.html /index.html;
    }
}
```

Включите сайт, отключите дефолт:

```bash
ln -s /etc/nginx/sites-available/music-exile /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Откройте в браузере `http://example.com` — должен открыться лонгрид (пока без HTTPS).

---

## 4. HTTPS (Let's Encrypt)

```bash
certbot --nginx -d example.com -d www.example.com
```

Certbot сам пропишет SSL в nginx и редирект с HTTP на HTTPS. Продление — автоматически (cron/systemd timer).

Проверка:

```bash
certbot renew --dry-run
```

---

## 5. Обновление после изменений в git

На VPS:

```bash
cd /var/www/A-Study-of-Music-in-Exile
git pull
cd web
npm ci          # только если менялся package-lock.json
npm run build
```

Пересборка занимает 1–2 минуты. Nginx перезапускать не нужно — он читает файлы из `out/` напрямую.

### Скрипт деплоя (опционально)

```bash
cat > /var/www/deploy-music-exile.sh << 'EOF'
#!/bin/bash
set -e
cd /var/www/A-Study-of-Music-in-Exile
git pull
cd web
npm ci
npm run build
echo "OK: $(date)"
EOF
chmod +x /var/www/deploy-music-exile.sh
```

Запуск: `/var/www/deploy-music-exile.sh`

---

## 6. Альтернатива: сборка на Mac, заливка на сервер

Если на VPS мало RAM (< 1 GB) и `npm run build` падает:

```bash
# На Mac
cd web
npm ci && npm run build

# Заливка только статики
rsync -avz --delete out/ root@ВАШ_IP:/var/www/A-Study-of-Music-in-Exile/web/out/
```

На сервере nginx уже смотрит в эту папку — достаточно `rsync`.

---

## 7. Частые проблемы

| Симптом | Решение |
|---------|---------|
| `dig` не показывает IP VPS | Подождать TTL DNS или проверить A-запись у регистратора |
| Certbot: failed to verify | DNS ещё не обновился; порт 80 закрыт (`ufw allow 'Nginx Full'`) |
| 404 на внутренних страницах | Проверить `try_files` в nginx (см. конфиг выше) |
| Пустая страница после деплоя | Убедиться, что `root` указывает на `web/out`, а не на `web/` |
| `npm run build` OOM на VPS | Собрать локально + `rsync` (раздел 6) |
| Старые картинки после обновления | Жёсткое обновление в браузере (Cmd+Shift+R) |

---

## 8. Чеклист перед публикацией

- [ ] DNS A-запись указывает на VPS
- [ ] `metadataBase` в `web/app/layout.tsx` = ваш домен
- [ ] `npm run build` проходит без ошибок
- [ ] Сайт открывается по HTTPS
- [ ] Боковая навигация, графики, карточки артистов работают
- [ ] Ссылка на GitHub внизу ведёт на [репозиторий](https://github.com/SlartyG/A-Study-of-Music-in-Exile)

---

Автор: Веселов Александр
