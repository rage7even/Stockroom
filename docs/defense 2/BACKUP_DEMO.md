# Орен · самостоятельный показ бэкапа и восстановления

Весь показ проходишь в свою очередь. Подготовь свой учебный заказ заранее. Сайт в Docker на **8001** показывает рабочую учебную базу. Сайт на **8002** покажет её состояние из снимка. Для этого команды ниже создадут временную копию проекта.

## 1. Открой рабочий сайт и создай заказ

В терминале **Ubuntu WSL** выполни:

```bash
cd '/mnt/d/KBTU/5 semestr/Basics of Information Systems/Stockroom_Study_Version/Stockroom_Study'
docker compose up -d --no-build
docker compose ps
```

1. Открой [Stockroom на 8001](http://127.0.0.1:8001). На экране входа нажми **Manager → Sign in**.
2. В **Products** найди **GaN 65W Fast Charger** (`BAS-C65W-WHT`). Если есть хотя бы одна доступная единица, можешь использовать этот товар. Иначе выбери другой SKU с доступным остатком.
3. Нажми **Orders → Create order**. Выбери **Almaty Mobile**, канал **Phone / sales manager**, товар и количество **1**. В заметку введи `Oren backup demo`. Нажми **Confirm & reserve stock**.
4. Открой новый заказ. Запиши его номер `ORD-...` и убедись, что статус **Confirmed**.

**Что сказать:** «Вот мой учебный заказ. Сейчас он подтверждён. Я сохраню это состояние, затем отменю заказ и покажу, как возвращается состояние из копии».

## 2. Создай и выгрузи снимок, пока заказ Confirmed

В том же терминале вставь блок целиком:

```bash
project_dir="$PWD"
restore_dir="$(mktemp -d /tmp/stockroom-restore.XXXXXX)"
snapshot="$restore_dir/backup-02-confirmed.db"

if output="$(docker compose exec -T stockroom python backend/manage.py maintenance --force-backup)"; then
  printf '%s\n' "$output"
  backup_path="$(printf '%s\n' "$output" | sed -n 's/^Backup created: //p')"
  if [ -n "$backup_path" ] && docker compose cp "stockroom:$backup_path" "$snapshot"; then
    ls -lh "$snapshot"
  else
    printf 'Снимок не выгружен. Проверь вывод команды.\n' >&2
  fi
fi
```

Продолжай после того, как `ls` покажет файл **`backup-02-confirmed.db`**. Блок берёт путь из строки `Backup created:` и сам даёт выгруженной копии короткое имя. Переменные сохраняются в этом терминале. Оставь его открытым.

## 3. Отмени заказ на 8001

В первой вкладке открой **Orders**, найди записанный номер и нажми **Cancel order → Confirm action**. Покажи статус **Cancelled**. Обновление страницы на 8001 перечитывает ту же базу, поэтому статус останется **Cancelled**. Снимок из шага 2 уже сохранён отдельным файлом.

## 4. Восстанови снимок и открой второй сайт

Вернись **в тот же терминал**, где сделал снимок. Блок использует установленное WSL-окружение проекта и готовую сборку Angular. Он копирует файлы приложения в папку из шага 2, восстанавливает снимок в её `backend/stockroom.db` и запускает второй сервер.

```bash
demo_python="$project_dir/.venv-linux/bin/python"

if [ ! -s "$snapshot" ]; then
  printf 'Сначала выгрузи снимок по шагу 2 в этом терминале.\n' >&2
elif [ ! -x "$demo_python" ]; then
  printf 'Сначала выполни python3 stockroom.py setup в папке проекта.\n' >&2
elif [ ! -f "$project_dir/frontend/dist/stockroom/browser/index.html" ]; then
  printf 'Нужна готовая сборка Angular. См. инструкцию по запуску.\n' >&2
else
  mkdir -p "$restore_dir/backend" "$restore_dir/integration" \
    "$restore_dir/frontend/dist/stockroom" &&
  cp -r "$project_dir/backend/config" "$project_dir/backend/inventory" \
    "$project_dir/backend/manage.py" "$restore_dir/backend/" &&
  cp "$project_dir/integration/restore.py" "$restore_dir/integration/" &&
  cp -r "$project_dir/frontend/dist/stockroom/browser" \
    "$restore_dir/frontend/dist/stockroom/" &&
  "$demo_python" "$restore_dir/integration/restore.py" "$snapshot" --server-stopped &&
  STOCKROOM_DB="$restore_dir/backend/stockroom.db" \
    "$demo_python" "$restore_dir/backend/manage.py" migrate --noinput &&
  STOCKROOM_DB="$restore_dir/backend/stockroom.db" \
    "$demo_python" "$restore_dir/backend/manage.py" runserver 127.0.0.1:8002 --noreload
fi
```

Дождись строки `Starting development server at http://127.0.0.1:8002/`. Оставь этот терминал открытым, пока показываешь результат. Если 8002 занят, замени его на 8003 в последней команде и в адресе браузера. После показа **Ctrl+C** остановит второй сервер.

## 5. Сравни один и тот же номер в двух вкладках

Открой [Stockroom на 8002](http://127.0.0.1:8002) в приватном окне браузера. Оставь 8001 в обычном окне. Оба сайта используют адрес `127.0.0.1`, и при входе в одном обычном окне их сессии могут перезаписать друг друга. На 8002 нажми **Manager → Sign in**, открой **Orders** и введи тот же номер. Статус должен быть **Confirmed**. Затем переключись на 8001 и покажи, что там тот же заказ **Cancelled**.

| Адрес | Что показывает | Статус заказа |
| --- | --- | --- |
| 8001 | Рабочая учебная база в Docker после отмены | **Cancelled** |
| 8002 | Состояние базы на момент снимка | **Confirmed** |

**Что сказать:** «В обеих вкладках один и тот же номер заказа. На 8001 видна отмена. На 8002 открыт восстановленный снимок, сделанный раньше, поэтому заказ снова подтверждён. Остальные данные на 8002 тоже относятся к моменту снимка».

Если на обоих сайтах **Cancelled**, проверь порт и номер заказа. Если они верные, снимок мог быть сделан после отмены. Создай новый учебный заказ и повтори шаги 1–5, делая снимок, пока видишь **Confirmed**. Старый бэкап сохранит тот статус, который был записан в нём.

## Что открыть в коде

- [compose.yaml](../../compose.yaml) — порт 8001 и том, подключённый к `/data`.
- [maintenance.py](../../backend/inventory/management/commands/maintenance.py) — `source.backup(copy)` создаёт снимок, `PRAGMA integrity_check` проверяет его.
- [restore.py](../../integration/restore.py) — проверка снимка и копирование в базу временного проекта. Для входа на восстановленном сайте используются новые сессии.

[Запуск Windows и WSL](../RUN_LOCAL.md) · [Часть Орена](05_INTEGRATION_BACKUP.md)
