import os
import re
import shutil
import tempfile
import zipfile
import logging
import subprocess
from pathlib import Path
from typing import Optional
from ftplib import FTP, error_perm

import requests
import pymysql

from telegram import Update, InputFile
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
NDK_PATH = os.getenv("NDK_PATH") or os.getenv("ANDROID_NDK_HOME") or ""

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

(
    COMPILE_JNI,
    COMPILE_HOST,
    COMPILE_NDK,
) = range(7, 10)

CONNECT_PATTERN = re.compile(
    r'(pRakClient->Connect\(\s*xorstr\(\s*")(\d{1,3}(?:\.\d{1,3}){3})("\s*)'
    r',\s*)(\d{1,5})(\s*,)',
    re.IGNORECASE,
)
HOST_PATTERN = re.compile(
    r"(\d{1,3}(?:\.\d{1,3}){3})\D+(\d{1,5})"
)


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


def find_jni_root(root: Path) -> Path | None:
    for candidate in root.rglob("Android.mk"):
        if candidate.parent.name.lower() == "jni":
            return candidate.parent
    hooks = list(root.rglob("hooks.cpp"))
    if hooks:
        return hooks[0].parent.parent if hooks[0].parent.name.lower() == "game" else hooks[0].parent
    jni_dirs = [p for p in root.rglob("*") if p.is_dir() and p.name.lower() == "jni"]
    return jni_dirs[0] if jni_dirs else None


def zip_directory(source: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in source.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(source.parent))
    return zip_path


def parse_host_port(text: str) -> tuple[str, int]:
    match = HOST_PATTERN.search(text.strip())
    if not match:
        raise ValueError("Не удалось разобрать IP и порт. Пример: 141.94.184.108 порт 2010")
    return match.group(1), int(match.group(2))


def patch_hooks_cpp(jni_root: Path, ip: str, port: int) -> Path:
    candidates = list(jni_root.rglob("hooks.cpp"))
    game_hooks = [
        path for path in candidates
        if "game" in [part.lower() for part in path.parts]
    ]
    hooks_file = game_hooks[0] if game_hooks else (candidates[0] if candidates else None)
    if not hooks_file:
        raise FileNotFoundError("Не найден hooks.cpp в JNI.")

    text = hooks_file.read_text(encoding="utf-8", errors="ignore")
    new_text, count = CONNECT_PATTERN.subn(
        rf"\g<1>{ip}\g<3>{port}\g<5>",
        text,
    )
    if count == 0:
        fallback = re.compile(
            r'(pRakClient->Connect\(\s*xorstr\(\s*")([^"]+)("\s*),\s*)(\d+)(\s*,)',
            re.IGNORECASE,
        )
        new_text, count = fallback.subn(
            rf"\g<1>{ip}\g<3>{port}\g<5>",
            text,
        )
    if count == 0:
        raise ValueError(
            "В hooks.cpp не найдена строка pRakClient->Connect(xorstr(\"...\"), порт, ...)."
        )
    hooks_file.write_text(new_text, encoding="utf-8")
    return hooks_file


def find_ndk_build(root: Path) -> Path:
    names = ("ndk-build", "ndk-build.cmd")
    direct = root / "ndk-build"
    if direct.is_file():
        return direct
    for name in names:
        for path in root.rglob(name):
            if path.is_file():
                return path
    raise FileNotFoundError("Не найден ndk-build. Укажите папку NDK или zip с ним.")


def download_url_file(url: str, destination: Path):
    url = url.strip()
    if "drive.google.com" in url or "drive.usercontent.google.com" in url:
        download_google_drive_file(url, str(destination))
        return destination

    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()
    with open(destination, "wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file.write(chunk)
    return destination


def resolve_ndk_build(source: str, work_dir: Path) -> Path:
    source = source.strip()
    path = Path(source).expanduser()
    if path.exists():
        if path.is_file() and path.name.startswith("ndk-build"):
            return path
        return find_ndk_build(path)

    if source.startswith("http://") or source.startswith("https://"):
        archive = work_dir / "ndk_download"
        download_url_file(source, archive)
        extract_dir = work_dir / "ndk"
        extract_dir.mkdir(exist_ok=True)
        if zipfile.is_zipfile(archive):
            extract_zip(str(archive), str(extract_dir))
            return find_ndk_build(extract_dir)
        raise ValueError("По ссылке пришёл не ZIP.")

    raise FileNotFoundError("Нужен путь к NDK, ссылка или zip-файл.")


async def run_compile_and_send(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ndk_build: Path,
    status_message,
):
    work_dir = Path(context.user_data["compile_dir"])
    os.chmod(ndk_build, 0o755)
    await status_message.edit_text("⚙️ Компилирую JNI (ndk-build)...")
    so_files = compile_jni(Path(context.user_data["jni_root"]), ndk_build)
    await status_message.edit_text("✅ Сборка готова, отправляю .so")
    for so_file in so_files:
        with open(so_file, "rb") as file:
            await update.message.reply_document(
                document=InputFile(file, filename=so_file.name),
                caption=f"📦 {so_file.name}",
            )
    shutil.rmtree(work_dir, ignore_errors=True)
    context.user_data.clear()


def compile_jni(jni_root: Path, ndk_build: Path) -> list[Path]:
    project_root = jni_root.parent if jni_root.name.lower() == "jni" else jni_root
    command = [str(ndk_build), "-C", str(project_root), "-j4"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        log = (result.stdout or "") + "\n" + (result.stderr or "")
        raise RuntimeError(f"ndk-build завершился с ошибкой:\n{log[-3500:]}")

    so_files = list(project_root.rglob("*.so"))
    if not so_files:
        libs = project_root / "libs"
        so_files = list(libs.rglob("*.so")) if libs.exists() else []
    if not so_files:
        raise FileNotFoundError("Сборка прошла, но .so файлы не найдены.")
    return so_files


async def download_telegram_document(update: Update, destination: Path):
    document = update.message.document
    if not document:
        raise ValueError("Нужно отправить файл.")
    file = await document.get_file()
    await file.download_to_drive(custom_path=str(destination))
    return destination


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

        jni_root = find_jni_root(root)
        if jni_root:
            jni_zip = Path(work_directory) / "jni.zip"
            zip_directory(jni_root, jni_zip)
            if jni_zip.stat().st_size <= 49 * 1024 * 1024:
                with open(jni_zip, "rb") as file:
                    await update.message.reply_document(
                        document=InputFile(file, filename="jni.zip"),
                        caption=(
                            "📁 Вот JNI из мода.\n"
                            "Чтобы собрать .so, отправьте /compile "
                            "и пришлите этот архив обратно."
                        ),
                    )
            else:
                await update.message.reply_text(
                    "JNI найден, но архив слишком большой для Telegram. "
                    "Отправьте его боту через /compile вручную."
                )
        else:
            await update.message.reply_text(
                "JNI в моде не найден. Если он у вас есть — /compile."
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
    work_dir = context.user_data.get("compile_dir")
    if work_dir:
        shutil.rmtree(work_dir, ignore_errors=True)
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Операция отменена."
    )

    return ConversationHandler.END


async def compile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    work_dir = tempfile.mkdtemp(prefix="jni_compile_")
    context.user_data["compile_dir"] = work_dir

    await update.message.reply_text(
        "🛠 Компиляция JNI\n\n"
        "Пришлите ZIP с JNI (тот, который бот отправил после установки мода)."
    )
    return COMPILE_JNI


async def compile_receive_jni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work_dir = Path(context.user_data["compile_dir"])
    archive_path = work_dir / "jni.zip"

    try:
        await download_telegram_document(update, archive_path)
        extract_dir = work_dir / "jni_src"
        extract_dir.mkdir(exist_ok=True)
        extract_zip(str(archive_path), str(extract_dir))
        jni_root = find_jni_root(extract_dir)
        if not jni_root:
            raise FileNotFoundError("В архиве не найден JNI (Android.mk / hooks.cpp).")
        context.user_data["jni_root"] = str(jni_root)
    except Exception as error:
        logger.exception("JNI archive error")
        await update.message.reply_text(f"❌ Не удалось принять JNI: {error}")
        return COMPILE_JNI

    await update.message.reply_text(
        "✅ JNI получен.\n\n"
        "Отправьте IP и порт хоста.\n"
        "Пример: 141.94.184.108 порт 2010"
    )
    return COMPILE_HOST


async def compile_receive_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ip, port = parse_host_port(update.message.text or "")
        await delete_user_message(update)
        context.user_data["compile_ip"] = ip
        context.user_data["compile_port"] = port
        jni_root = Path(context.user_data["jni_root"])
        hooks_file = patch_hooks_cpp(jni_root, ip, port)
    except Exception as error:
        await update.message.reply_text(f"❌ {error}")
        return COMPILE_HOST

    if NDK_PATH:
        status = await update.message.reply_text(
            f"✅ Подставил {ip}:{port} в {hooks_file.name}.\n"
            f"Использую NDK с сервера: {NDK_PATH}"
        )
        try:
            ndk_build = resolve_ndk_build(NDK_PATH, Path(context.user_data["compile_dir"]))
            await run_compile_and_send(update, context, ndk_build, status)
        except Exception as error:
            logger.exception("JNI compile error")
            await status.edit_text(f"❌ Ошибка компиляции:\n{error}")
            shutil.rmtree(context.user_data.get("compile_dir"), ignore_errors=True)
            context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Подставил {ip}:{port} в {hooks_file.name}.\n\n"
        "Пришлите NDK одним из способов:\n"
        "• ZIP-файл\n"
        "• ссылка (http/https или Google Drive)\n"
        "• путь на сервере, например /opt/android-ndk"
    )
    return COMPILE_NDK


async def compile_receive_ndk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work_dir = Path(context.user_data["compile_dir"])
    status = await update.message.reply_text("📥 Готовлю NDK...")

    try:
        if update.message.document:
            ndk_zip = work_dir / "ndk.zip"
            await download_telegram_document(update, ndk_zip)
            ndk_dir = work_dir / "ndk"
            ndk_dir.mkdir(exist_ok=True)
            await status.edit_text("📦 Распаковываю NDK...")
            extract_zip(str(ndk_zip), str(ndk_dir))
            ndk_build = find_ndk_build(ndk_dir)
        else:
            text = (update.message.text or "").strip()
            await status.edit_text("📥 Загружаю / ищу NDK...")
            ndk_build = resolve_ndk_build(text, work_dir)

        await run_compile_and_send(update, context, ndk_build, status)
    except Exception as error:
        logger.exception("JNI compile error")
        text = str(error)
        if len(text) > 3500:
            log_path = work_dir / "compile_error.txt"
            log_path.write_text(text, encoding="utf-8")
            await status.edit_text("❌ Ошибка компиляции, лог во вложении.")
            with open(log_path, "rb") as file:
                await update.message.reply_document(
                    document=InputFile(file, filename="compile_error.txt")
                )
        else:
            await status.edit_text(f"❌ Ошибка компиляции:\n{text}")
        shutil.rmtree(work_dir, ignore_errors=True)
        context.user_data.clear()

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

    compile_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("compile", compile_start)
        ],
        states={
            COMPILE_JNI: [
                MessageHandler(
                    filters.Document.ALL,
                    compile_receive_jni,
                )
            ],
            COMPILE_HOST: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    compile_receive_host,
                )
            ],
            COMPILE_NDK: [
                MessageHandler(
                    filters.Document.ALL,
                    compile_receive_ndk,
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    compile_receive_ndk,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )
    application.add_handler(compile_conversation)

    logger.info("Bot started")
    application.run_polling()


if __name__ == "__main__":
    main()
