# Stockroom в Windows и WSL

В корне проекта есть общий скрипт `stockroom.py`. Он готовит зависимости и базу через существующие команды Django. Сервер отдаёт готовый Angular, а при запуске проверяет, пора ли создать резервную копию. Для запуска учебной версии нужен Python 3.11 или новее и готовая сборка Angular. В этом архиве сборка уже есть.

## Windows PowerShell

Откройте папку `Stockroom_Study` в терминале и выполните:

```powershell
python stockroom.py setup
python stockroom.py run
```

Если Python запускается через `py`, используйте `py -3 stockroom.py setup` и `py -3 stockroom.py run`.

## WSL в VS Code

1. Установите расширение **WSL** от Microsoft в VS Code на Windows.
2. В терминале своего дистрибутива WSL перейдите в папку проекта и откройте её:

   ```bash
   cd '/mnt/d/KBTU/5 semestr/Basics of Information Systems/Stockroom_Study_Version/Stockroom_Study'
   code .
   ```

   Из уже открытого VS Code можно использовать команду **WSL: Reopen Folder in WSL**. Когда появится отметка **WSL** внизу окна, откройте встроенный терминал. [Документация VS Code](https://code.visualstudio.com/docs/remote/wsl)

3. В терминале WSL выполните:

   ```bash
   python3 --version
   python3 stockroom.py setup
   python3 stockroom.py run
   ```

   В проверенной Ubuntu установлен Python 3.14, а пакет для создания окружения отсутствует. Выполните `sudo apt install python3.14-venv`, затем повторите `setup`. Для другого дистрибутива используйте пакет `venv` для своей версии Python. Первый запуск `setup` загружает Python-зависимости, которых ещё нет в окружении.

Откройте [http://127.0.0.1:8000](http://127.0.0.1:8000) в браузере Windows. Для остановки используйте Ctrl+C в WSL или Ctrl+Break в Windows. Если 8000 занят, укажите свободный порт, например `--port 8003`. Docker по умолчанию использует 8001, а сценарий восстановления — 8002. Для проверки с телефона используйте развёрнутый адрес, доступный с телефона. [Сеть WSL](https://learn.microsoft.com/en-us/windows/wsl/networking)

`setup` нужен при первой настройке окружения или после изменения зависимостей и миграций. В учебной базе он также добавляет недостающие аккаунты Shop (Sales) и Tech Support и учебный каталог. При обычном запуске достаточно `run`. В Windows скрипт использует `.venv-windows`, если это окружение подготовлено, или `.venv`. В WSL и Linux используется `.venv-linux`. В одной папке эти запуски используют `backend/stockroom.db`. При переключении сначала остановите предыдущий сервер.

## Когда нужно пересобрать интерфейс

Если готовой сборки нет или изменился Angular, соберите его из папки `frontend`. В Windows используйте `npm.cmd ci` и `npm.cmd run build`. В WSL используйте `npm ci` и `npm run build` с Linux-версией Node.js. Для регулярной пересборки в WSL удобнее держать отдельную копию проекта в домашней папке Linux. У неё будут собственные зависимости, сборка и база. [Совместимость Angular](https://angular.dev/reference/versions) · [Файловые системы Windows и WSL](https://learn.microsoft.com/en-us/windows/wsl/interop)

## Docker и хостинг

В терминале WSL из корня `Stockroom_Study`:

```bash
docker compose up -d --build
docker compose ps
```

Откройте [http://127.0.0.1:8001](http://127.0.0.1:8001). Сборка устанавливает зависимости и собирает Angular внутри Docker. При запуске контейнер применяет миграции и добавляет недостающие учебные аккаунты и товары в свою базу. Порт 8001 позволяет одновременно держать открытым запуск через Python на 8000. Для выбора другого порта используйте `STOCKROOM_PORT=8003 docker compose up -d`.

Если образ уже собран, достаточно `docker compose up -d --no-build`. Для регулярной пересборки в WSL держите рабочую копию исходников в домашней папке Linux. Сборка из `/mnt/d` может долго читать файлы. [Файловые системы Windows и WSL](https://learn.microsoft.com/en-us/windows/wsl/interop)

`docker compose logs -f stockroom` показывает журнал. `docker compose stop` останавливает приложение. `docker compose up -d` запускает его снова. База и бэкапы хранятся в томе `stockroom_stockroom-data`. Том сохраняется при обычном `docker compose down`, а `docker compose down -v` удаляет его вместе с данными. [Тома Docker](https://docs.docker.com/engine/storage/volumes/)

Чтобы создать снимок вручную и скопировать папку с ним из контейнера:

```bash
docker compose exec stockroom python backend/manage.py maintenance --force-backup
docker compose cp stockroom:/data/backups ./stockroom-docker-backups
```

Экспортированный снимок можно восстановить на отдельной локальной копии проекта по [сценарию восстановления](defense%202/BACKUP_DEMO.md). Этот Compose настроен для локального показа с ноутбука.

Для публичного хостинга сначала проверьте, как выбранная площадка запускает приложения. Docker удобен, если площадка принимает образ контейнера. Для SQLite и бэкапов на таком хостинге нужно постоянное хранилище. При пересоздании контейнера база должна остаться доступной. Публичной версии также нужны рабочие настройки Django и производственный сервер. [Тома Docker](https://docs.docker.com/engine/storage/volumes/) · [Развёртывание Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
