import os
import re
import shutil
import tempfile
import zipfile
import logging
from pathlib import Path
from ftplib import FTP, error_perm

import requests
import pymysql

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8997041433:AAGFovAeMMezBm1R7UteEQEyRG7Ti5Nzwlo")
GOOGLE_DRIVE_URL = (
    "https://drive.google.com/file/d/"
    "1V-kWefqqzE8MjCrGdE5xntzqHhLWFf3s/view"
)
FTP_REMOTE_PATH = "/"
MYSQL_INI_PATH = "scriptfiles/laird_mysql.ini"
SQL_COMMANDS = []

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

(
    FTP_USERNAME,
    FTP_PASSWORD,
    FTP_HOST,
    DB_HOST,
    DB_USERNAME,
    DB_PASSWORD,
    DB_NAME,
) = range(7)


def extract_google_drive_file_id(url: str) -> str:
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Не удалось определить ID файла Google Drive.")


def download_google_drive_file(url: str, destination: str):
    file_id = extract_google_drive_file_id(url)
    session = requests.Session()

    download_url = (
        "https://drive.usercontent.google.com/download"
        f"?id={file_id}&export=download&confirm=t"
    )

    response = session.get(
        download_url,
        stream=True,
        timeout=120,
    )
    response.raise_for_status()

    with open(destination, "wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file.write(chunk)

    response.close()
    return destination


def extract_zip(zip_path: str, destination: str):
    base_path = Path(destination).resolve()

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            member_path = (base_path / member.filename).resolve()
            if not str(member_path).startswith(str(base_path)):
                raise ValueError("ZIP содержит небезопасный путь.")
        archive.extractall(destination)


def find_mysql_ini(root: Path):
    expected = root / MYSQL_INI_PATH
    if expected.is_file():
        return expected

    for path in root.rglob("laird_mysql.ini"):
        if path.is_file():
            return path

    return None


def modify_mysql_ini(root: Path, db_username: str, db_password: str):
    ini_file = find_mysql_ini(root)

    if not ini_file:
        raise FileNotFoundError(
            "В моде не найден scriptfiles/laird_mysql.ini"
        )

    text = ini_file.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    new_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.lower().startswith("username"):
            line = f"username = {db_username}"
        elif stripped.lower().startswith("password"):
            line = f"password = {db_password}"
        elif stripped.lower().startswith("database"):
            line = f"database = {db_username}"

        new_lines.append(line)

    new_text = "\n".join(new_lines)

    if text.endswith("\n"):
        new_text += "\n"

    ini_file.write_text(new_text, encoding="utf-8")
    return ini_file


def test_ftp_connection(host: str, username: str, password: str):
    ftp = FTP()
    ftp.connect(host=host, port=21, timeout=30)
    ftp.login(user=username, passwd=password)
    ftp.quit()


def ensure_remote_directory(ftp: FTP, path: str):
    parts = [part for part in path.split("/") if part]
    current = ""

    for part in parts:
        current += "/" + part
        try:
            ftp.cwd(current)
        except error_perm:
            ftp.mkd(current)
            ftp.cwd(current)


def upload_directory_to_ftp(
    host: str,
    username: str,
    password: str,
    local_root: Path,
    remote_root: str,
):
    ftp = FTP()
    ftp.connect(host=host, port=21, timeout=60)
    ftp.login(user=username, passwd=password)
    ftp.set_pasv(True)

    for local_file in local_root.rglob("*"):
        if not local_file.is_file():
            continue

        relative_path = local_file.relative_to(local_root)

        remote_directory = (
            remote_root.rstrip("/")
            + "/"
            + str(relative_path.parent).replace("\\", "/")
        )

        if remote_directory.endswith("/."):
            remote_directory = remote_root

        try:
            ftp.cwd(remote_directory)
        except error_perm:
            ensure_remote_directory(ftp, remote_directory)

        with open(local_file, "rb") as file:
            ftp.storbinary(
                f"STOR {relative_path.name}",
                file,
                blocksize=1024 * 256,
            )

    ftp.quit()


def test_mysql_connection(
    host: str,
    username: str,
    password: str,
    database: str,
):
    connection = pymysql.connect(
        host=host,
        user=username,
        password=password,
        database=database,
        connect_timeout=15,
        charset="utf8mb4",
    )
    connection.close()


def execute_sql_commands(
    host: str,
    username: str,
    password: str,
    database: str,
):
    if not SQL_COMMANDS:
        return 0

    connection = pymysql.connect(
        host=host,
        user=username,
        password=password,
        database=database,
        connect_timeout=15,
        charset="utf8mb4",
        autocommit=True,
    )

    cursor = connection.cursor()
    executed = 0

    try:
        for sql in SQL_COMMANDS:
            if not sql.strip():
                continue
            cursor.execute(sql)
            executed += 1
    finally:
        cursor.close()
        connection.close()

    return executed


async def delete_user_message(update: Update):
    try:
        if update.message:
            await update.message.delete()
    except Exception:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "👋 Добро пожаловать!\n\n"
        "Я установлю мод на ваш сервер.\n\n"
        "🔐 Отправьте логин FTP."
    )

    return FTP_USERNAME


async def receive_ftp_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["ftp_username"] = update.message.text.strip()
    await delete_user_message(update)

    await update.message.reply_text("🔑 Отправьте пароль FTP.")
    return FTP_PASSWORD


async def receive_ftp_password(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["ftp_password"] = update.message.text.strip()
    await delete_user_message(update)

    await update.message.reply_text("🌐 Отправьте удалённый хост FTP.")
    return FTP_HOST


async def receive_ftp_host(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["ftp_host"] = update.message.text.strip()
    await delete_user_message(update)

    await update.message.reply_text("⏳ Проверяю FTP...")

    try:
        test_ftp_connection(
            context.user_data["ftp_host"],
            context.user_data["ftp_username"],
            context.user_data["ftp_password"],
        )
    except Exception:
        logger.exception("FTP connection error")
        await update.message.reply_text(
            "❌ Не удалось подключиться к FTP.\n"
            "Проверьте данные и начните заново через /start."
        )
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ FTP подключён!\n\n"
        "🌐 Отправьте хост базы данных."
    )

    return DB_HOST


async def receive_db_host(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["db_host"] = update.message.text.strip()
    await delete_user_message(update)

    await update.message.reply_text("👤 Отправьте логин базы данных.")
    return DB_USERNAME


async def receive_db_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["db_username"] = update.message.text.strip()
    await delete_user_message(update)

    await update.message.reply_text("🔑 Отправьте пароль базы данных.")
    return DB_PASSWORD


async def receive_db_password(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["db_password"] = update.message.text.strip()
    await delete_user_message(update)

    await update.message.reply_text("🗄️ Отправьте название базы данных.")
    return DB_NAME


async def receive_db_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["db_name"] = update.message.text.strip()
    await delete_user_message(update)

    status = await update.message.reply_text(
        "🚀 Все данные получены.\nНачинаю установку..."
    )

    work_directory = tempfile.mkdtemp(prefix="mod_installer_")

    try:
        await status.edit_text(
            "📥 Шаг 1/5\nСкачиваю мод с Google Drive..."
        )

        archive_path = os.path.join(work_directory, "mod.zip")

        download_google_drive_file(
            GOOGLE_DRIVE_URL,
            archive_path,
        )

        await status.edit_text(
            "📦 Шаг 2/5\nРаспаковываю мод..."
        )

        mod_directory = os.path.join(work_directory, "mod")
        os.makedirs(mod_directory, exist_ok=True)

        extract_zip(archive_path, mod_directory)

        root = Path(mod_directory)

        await status.edit_text(
            "⚙️ Шаг 3/5\nНастраиваю laird_mysql.ini..."
        )

        modify_mysql_ini(
            root=root,
            db_username=context.user_data["db_username"],
            db_password=context.user_data["db_password"],
        )

        await status.edit_text(
            "📤 Шаг 4/5\nЗагружаю мод на FTP..."
        )

        upload_directory_to_ftp(
            host=context.user_data["ftp_host"],
            username=context.user_data["ftp_username"],
            password=context.user_data["ftp_password"],
            local_root=root,
            remote_root=FTP_REMOTE_PATH,
        )

        await status.edit_text(
            "🗄️ Шаг 5/5\nПроверяю подключение к базе данных..."
        )

        test_mysql_connection(
            host=context.user_data["db_host"],
            username=context.user_data["db_username"],
            password=context.user_data["db_password"],
            database=context.user_data["db_name"],
        )

        executed = execute_sql_commands(
            host=context.user_data["db_host"],
            username=context.user_data["db_username"],
            password=context.user_data["db_password"],
            database=context.user_data["db_name"],
        )

        await status.edit_text(
            "✅ Установка завершена!\n\n"
            "📦 Мод загружен на FTP.\n"
            "⚙️ laird_mysql.ini настроен.\n"
            "🗄️ Подключение к БД успешно.\n"
            f"📝 SQL-команд выполнено: {executed}"
        )

    except Exception as error:
        logger.exception("Installation error")

        await status.edit_text(
            "❌ Произошла ошибка при установке.\n\n"
            f"Причина: {error}"
        )

    finally:
        shutil.rmtree(work_directory, ignore_errors=True)
        context.user_data.clear()

    return ConversationHandler.END


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Установка отменена."
    )

    return ConversationHandler.END


def main():
    if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_ТОКЕН_БОТА":
        raise RuntimeError("Не задан BOT_TOKEN.")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start)
        ],
        states={
            FTP_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_ftp_username,
                )
            ],
            FTP_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_ftp_password,
                )
            ],
            FTP_HOST: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_ftp_host,
                )
            ],
            DB_HOST: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_db_host,
                )
            ],
            DB_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_db_username,
                )
            ],
            DB_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_db_password,
                )
            ],
            DB_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_db_name,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    application.add_handler(conversation)

    logger.info("Bot started")
    application.run_polling()


if __name__ == "__main__":
    main()
