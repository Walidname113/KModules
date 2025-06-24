__version__ = (1, 1, 7)
# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of Media-Downloader and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# meta developer: @RenaYugen
# requires: aiohttp mutagen python-ffmpeg
# meta APIs Providers: https://t.me/BJ_devs, https://t.me/Teleservices_api
# scope: hikka_only
# scope: hikka_min 1.6.2
# changelog: 1.1.7 change-log: added client_ready, changed meta developer, testing update system.

from hikkatl.types import Message
from .. import loader, utils
import aiohttp
import os
import tempfile
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from urllib.parse import urlparse
import asyncio
import re
import logging
import errno
import sys
import inspect
from pathlib import Path

log = logging.getLogger(f"Media-Downloader")

LINK_PATTERN = re.compile(
    r"(?:http[s]?://|www\.)[^\s\/]+?\.(?:com|net|org|io|ru|su|ua|jp)(?:[\/\w\-\.\?\=\&\%\#]*)",
    flags=re.IGNORECASE
)

class ConnectionResetByPeer(Exception):
    pass
    
@loader.tds
class MediaDownloaderMod(loader.Module):
    """👑 Multimedia Loader"""

    strings = {
        "name": "Media-Downloader",
        "no_url": "<emoji document_id=5278578973595427038>🚫</emoji> Provide a Spotify track URL.",
        "fetching": "<emoji document_id=6030657343744644592>🔄</emoji> Fetching data...",
        "api_error": "<emoji document_id=5278578973595427038>🚫</emoji> API request failed. Status: {}",
        "api_exception": "<emoji document_id=5278578973595427038>🚫</emoji> API request error: {}",
        "api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Failed to get track data.",
        "invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Invalid API data.",
        "downloading": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading track...",
        "download_error": "<emoji document_id=5278578973595427038>🚫</emoji> Error downloading track. Status: {}",
        "image_error": "<emoji document_id=5278578973595427038>🚫</emoji> Error downloading cover image. Status: {}",
        "file_error": "<emoji document_id=5278578973595427038>🚫</emoji> File download error: {}",
        "tag_error": "<emoji document_id=5278578973595427038>🚫</emoji> Error embedding cover: {}",
        "done_caption": "<emoji document_id=5318760565902947324>✅</emoji> Track successfully downloaded!\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "done_caption_minimal": "<emoji document_id=5318760565902947324>✅</emoji> Track succesfully downloaded!",
        "no_tiktok_url": "<emoji document_id=5278578973595427038>🚫</emoji> Provide a TikTok video URL.",
        "tiktok_api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Failed to get video data.",
        "tiktok_invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Invalid TikTok API data.",
        "tiktok_no_video": "<emoji document_id=5278578973595427038>🚫</emoji> No suitable videos found for download.",
        "downloading_hd": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading <b>HD</b> video...",
        "downloading_sd": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading video...",
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Video successfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Video succesfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Video succesfully downloaded!",
        "tiktok_success_minimal_sd": "<emoji document_id=5318760565902947324>✅</emoji> Video succesfully downloaded!",
        "cfg_show_tiktok_info": "Show author and link for TikTok message caption.",
        "cfg_show_spotify_link": "Show link for Spotify caption message.",
        "cfg_force_hd": "Always download HD (if available).",
        "auto_update_ch": "Autoupdate module when new versions.",
        "no_args_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Please provide a username and story number.",
        "invalid_format_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Format: tgsload <username> <story_number>`",
        "invalid_number_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> The story number must be a positive integer.",
        "api_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> API request error: {error}",
        "no_stories_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> No stories found.",
        "invalid_index_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Invalid story number. Available range: 1 - {max_index}",
        "no_url_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> The selected story has no URL.",
        "download_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Error downloading the file: {error}",
        "success_tgs": "<emoji document_id=5318760565902947324>✅</emoji> Story downloaded successfully!\n<emoji document_id=6039451237743595514>📎</emoji> <b>Story caption:</b> {caption}",
        "success_no_caption_tgs": "<emoji document_id=5318760565902947324>✅</emoji> Story downloaded successfully!",
        "downloading_tgs": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading story...",
        "cfg_show_caption_tgs": "Display captions for downloaded stories.",
        "cfg_filter_links": "Filter out links in story captions.",
        "ffmpeg_missing": "<emoji document_id=5278578973595427038>🚫</emoji> FFmpeg is not installed on the system. Install it <a href='https://t.me/hikka_talks/631886'>via this link</a>.",
        "yapi_error": "<emoji document_id=5278578973595427038>🚫</emoji> API error: <code>{}</code>.",
        "ysuccess": "<emoji document_id=4906943755644306322>🌐</emoji> <a href='{yurl}'>{ytitle}</a>\n\n<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Download successful!",
        "ysuccessm": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Download successful!",
        "yuploading": "<emoji document_id=5276220667182736079>⬇️</emoji> <b>[May take a while]</b> | Uploading result...",
        "yerror": "<emoji document_id=5278578973595427038>🚫</emoji> Error: <code>{}</code>.",
        "yno_media": "<emoji document_id=5278578973595427038>🚫</emoji> No media available",
        "yargs": "<emoji document_id=5278578973595427038>🚫</emoji> Provide a YouTube video link!",
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> No streams in allowed resolution! To fix, enter: .<code>fcfg Media-Downloader allow_high_res True</code>.",
        "config_allow_high_res": "Allow downloading >1080p60 | WARNING: If your device does not support more than 1080p, enabling this setting makes no sense.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>BETA version warning!</b>\n\nAll commands labeled <b>BETA/ALPHA/TEST</b> are potentially unstable. This means these commands may often cause errors, malfunction, or not work at all, and sometimes even <b>break the entire module</b>. If you want to avoid this, it is advised to stop using these commands and wait until they are stable. Beta versions are released only after testing, so errors causing total module failure are <b>almost always excluded</b>, but there is no guarantee they won’t occur.",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Server closed connection (104). Possible solution: Enable blocking of video up to 1080p60 in module config (<code>allow_high_res</code>), if it does not help: check the speed of the Internet connection.",
        "show_ytdlh_vname": "Show the title of a YouTube video when it is loaded?",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg return Error: <code>{retcode}</code>.",
        "rrs": "[Useful] Channel with information about modules from the developer.",
        "_cls_doc": "👑 The best module designed to let you download the media you want without watermarks, service subscription, or author attribution in F/-HD."
    }

    strings_ru = {
        "name": "Media-Downloader",
        "no_args_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Укажите имя пользователя и номер истории.",
        "invalid_format_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Формат: tgsload <имя_пользователя> <номер_истории>`",
        "invalid_number_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Номер истории должен быть положительным числом.",
        "api_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при запросе API: {error}",
        "no_stories_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Истории не найдены.",
        "invalid_index_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Неверный номер истории. Доступный диапазон: 1 - {max_index}",
        "no_url_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> У выбранной истории отсутствует URL.",
        "download_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при загрузке файла: {error}",
        "success_tgs": "<emoji document_id=5318760565902947324>✅</emoji> История успешно загружена!\n<emoji document_id=6039451237743595514>📎</emoji> <b>Описание:</b> {caption}",
        "success_no_caption_tgs": "<emoji document_id=5318760565902947324>✅</emoji> История успешно загружена!",
        "downloading_tgs": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю историю...",
        "cfg_show_caption_tgs": "Показывать описание у загружаемых историй.",
        "no_url": "<emoji document_id=5278578973595427038>🚫</emoji> Укажи ссылку на трек Spotify.",
        "fetching": "<emoji document_id=6030657343744644592>🔄</emoji> Получаю данные...",
        "api_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при запросе к API. Статус: {}",
        "api_exception": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при запросе к API: {}",
        "api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Не удалось получить данные трека.",
        "invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Неверные данные от API.",
        "downloading": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю трек...",
        "download_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при скачивании трека. Статус: {}",
        "image_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при скачивании обложки. Статус: {}",
        "file_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при скачивании файлов: {}",
        "tag_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при добавлении обложки: {}",
        "done_caption": "<emoji document_id=5318760565902947324>✅</emoji> Трек успешно загружен!\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "done_caption_minimal": "<emoji document_id=5318760565902947324>✅</emoji> Трек успешно загружен!",
        "no_tiktok_url": "<emoji document_id=5278578973595427038>🚫</emoji> Укажи ссылку на видео TikTok.",
        "tiktok_api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Не удалось получить данные видео.",
        "tiktok_invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Некорректные данные от TikTok API.",
        "tiktok_no_video": "<emoji document_id=5278578973595427038>🚫</emoji> Не найдено подходящих видео для загрузки.",
        "downloading_hd": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю <b>HD</b> видео...",
        "downloading_sd": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю видео...",
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Видео успешно загружено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Видео успешно загружено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Видео успешно загружено!",
        "tiktok_success_minimal_sd": "<emoji document_id=5318760565902947324>✅</emoji> Видео успешно загружено!",
        "cfg_show_tiktok_info": "Показывать автора и ссылку в TikTok.",
        "cfg_show_spotify_link": "Показывать ссылку в Spotify.",
        "cfg_force_hd": "Всегда загружать видео в HD (если доступно).",
        "auto_update_ch": "Автообновлять модуль при новых версиях.",
        "cfg_filter_links": "Фильтровать ли ссылки в описаниях к историям при их загрузке.",
        "ffmpeg_missing": "<emoji document_id=5278578973595427038>🚫</emoji> FFmpeg не установлен в системе. Установите <a href='https://t.me/hikka_talks/631886'>по ссылке</a>.",
        "yapi_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка API: <code>{}</code>.",
        "ysuccess": "<emoji document_id=4906943755644306322>🌐</emoji> <a href='{yurl}'>{ytitle}</a>\n\n<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Загружено успешно!",
        "ysuccessm": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Загружено успешно!",
        "yuploading": "<emoji document_id=5276220667182736079>⬇️</emoji> <b>[Может быть долго]</b> | Загружаю результат...",
        "yerror": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка: <code>{}</code>.",
        "yno_media": "<emoji document_id=5278578973595427038>🚫</emoji> Нет доступных медиа",
        "yargs": "<emoji document_id=5278578973595427038>🚫</emoji> Укажи ссылку на YouTube видео!",           
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> Нет потоков в разрешенном разрешении! Чтобы исправить, введите: .<code>fcfg Media-Downloader allow_high_res True</code> <b>(Не всегда помогает)</b>.",
        "config_allow_high_res": "Разрешить скачивание >1080p60 | WARNING: Если ваше устройство не поддерживает больше чем 1080р, смысла разрешать эту настройку нет.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>Предупреждение о BETA-версиях!</b>\n\nВсе команды, которые имеют инициалы <b>BETA/ALPHA/TEST</b> — потенциально нестабильны. Это значит, что эти команды могут часто вызывать ошибки или неправильно работать, или вовсе не работать, а иногда и вообще <b>сломать работу всего модуля</b>. Если вы не хотите этого, советуется больше не использовать эти команды, и ждать пока они будут стабильно реализованы. Бета версии выходят только после их тестирования, так что ошибки по типу полной поломки модуля <b>почти всегда исключены</b>, но нету гарантии что их не будет.",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Сервер закрыл соединение (104). Возможные решения: Включить блокировку максимального качества загрузки видео в 1080р60 в конфиге модуля (<code>allow_high_res</code>), если не помогает, то проверить скорость интернета. Скорее всего, видео слишком долгое/качественное, от чего занимает слишком много места.",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg вернул ошибку: <code>{retcode}</code>.",
        "show_ytdlh_vname": "Показывать ли название видео при загрузке с YouTube?",
        "rrs": "[Полезно] Канал с информацией о модулях от разработчика.",
        "_cls_doc": "👑 Лучший модуль, который поможет загрузить нужное вам медиа без водяного знака/подписки сервиса/автора в F/-HD."
    }

    async def client_ready(self, client, db):
        self.client = client
        self.db = db        
        await self.request_join(
            "@KiyatsukaModules",
            self.strings['rrs'],
        )
    
    @loader.loop(300, autostart=True)
    async def check_for_updates(self):
        if not self.config.get("auto_update", True):
            return

        metadata_url = "https://raw.githubusercontent.com/Walidname113/KModules/hikka/Media-Downloader.py"

        try:
            module = sys.modules[__name__]
            sys_module = inspect.getmodule(module)
            local_version = ".".join(map(str, sys_module.__version__))
        except Exception:
            log.warning("Local version not found in __version__")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(metadata_url) as resp:
                    if resp.status != 200:
                        return
                    remote_text = await resp.text()
        except Exception as e:
            log.warning(f"Failed to fetch metadata: {e}")
            return

        try:
            first_line = remote_text.splitlines()[0]
            if "__version__" not in first_line:
                return
            remote_version = (
                first_line.split("=", 1)[1]
                .strip()
                .strip("()")
                .replace(",", "")
                .replace(" ", ".")
            )
        except Exception:
            log.warning("Failed to parse remote version")
            return

        if remote_version != local_version:
            log.info(f"New version detected: {remote_version}, updating...")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(metadata_url) as resp:
                        if resp.status != 200:
                            return
                        new_code = await resp.text()
            except Exception as e:
                log.warning(f"Failed to download new code: {e}")
                return

            try:
                module_path = Path(sys_module.__file__).resolve()
                with open(module_path, "w", encoding="utf-8") as f:
                    f.write(new_code)
                log.info(f"Module successfully updated to {remote_version}, restart required.")
            except Exception as e:
                log.warning(f"Failed to write new code: {e}")

    def catch_connection_reset(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                cause = getattr(e, "__cause__", None)
                context = getattr(e, "__context__", None)

                if isinstance(e, ConnectionResetError) or \
                   isinstance(cause, ConnectionResetError) or \
                   isinstance(context, ConnectionResetError) or \
                   "Connection reset by peer" in str(e) or "104" in str(e):
                    raise ConnectionResetByPeer("server return 104 ERROR.")

                raise
        return wrapper                
                                                
    async def _check_ffmpeg(self):
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        return proc.returncode == 0

    @catch_connection_reset
    async def _fetch_json(self, session, url, params=None):
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()
                
    @catch_connection_reset                    
    async def _download_file(self, session, url, filename):
        async with session.get(url) as resp:
            resp.raise_for_status()
            with open(filename, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)

    async def _merge_video_audio(self, video_path, audio_path, output_path):
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-y",
            output_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        return proc.returncode

    def _is_resolution_allowed(self, stream):
        if self.config["allow_high_res"]:
            return True
            
        height = stream.get("height", 0)
        fps = stream.get("fps", 30)
        
        if height <= 1080:
            if height == 1080 and fps > 60:
                return False
            return True
            
        return False

    def __init__(self):
        super().__init__()
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "show_tiktok_info", True,
                doc=lambda: self.strings("cfg_show_tiktok_info"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_spotify_link", True,
                doc=lambda: self.strings("cfg_show_spotify_link"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "force_hd", True,
                doc=lambda: self.strings("cfg_force_hd"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "auto_update", True,
                doc=lambda: self.strings("auto_update_ch"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_caption",
                True,
                doc=lambda: self.strings("cfg_show_caption_tgs"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "filter_links", False,
                doc=lambda: self.strings("cfg_filter_links"),
                validator=loader.validators.Boolean(),
            ),            
            loader.ConfigValue(
                "allow_high_res",
                False,
                doc=lambda: self.strings("config_allow_high_res"),
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "show_ytname",
                False,
                doc=lambda: self.strings("show_ytdlh_vname"),
                validator=loader.validators.Boolean()
            )
        )
        
    @loader.command(ru_doc=f"Скачать видео из TikTok.\nИспользование: .tikload <ссылка>",
                    en_doc=f"Download TikTok video.\nUsage: .tikload <link>")
    async def tikloadcmd(self, message: Message):
        """This command downloads videos from TikTok."""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_tiktok_url"])
            return

        url = args.strip()
        api_url = f"https://tiktok-downloader.apis-bj-devs.workers.dev?url={url}"
      # await utils.answer(message, self.strings["fetching"])

        data = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        await utils.answer(message, self.strings["api_error"].format(resp.status))
                        return
                    data = await resp.json()
        except Exception as e:
            await utils.answer(message, self.strings["api_exception"].format(e))
            return

        if not data or not data.get("success"):
            await utils.answer(message, self.strings["tiktok_api_fail"])
            return

        video_data = None
        quality = ""
        preferred = ["download_video_hd", "download_video_480p"]

        if not self.config["force_hd"]:
            preferred.reverse()

        for q in preferred:
            for item in data.get("downloads", []):
                if item["type"] == q:
                    video_data = item
                    quality = "hd" if "hd" in q else "sd"
                    break
            if video_data:
                break

        if not video_data and not self.config["force_hd"]:
            fallback_url = f"https://tele-social.vercel.app/down?url={url}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(fallback_url) as resp:
                        if resp.status == 200:
                            alt_data = await resp.json()
                            if alt_data.get("status") and "video" in alt_data.get("data", {}):
                                video_data = {"url": alt_data["data"]["video"]}
                                quality = "sd"
            except Exception:
                pass

        if not video_data:
            await utils.answer(message, self.strings["tiktok_no_video"])
            return

        await utils.answer(message, self.strings["downloading_hd"] if quality == "hd" else self.strings["downloading_sd"])

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_data["url"]) as resp:
                        if resp.status != 200:
                            await utils.answer(message, self.strings["download_error"].format(resp.status))
                            return
                        with open(video_path, "wb") as f:
                            f.write(await resp.read())
            except Exception as e:
                await utils.answer(message, self.strings["file_error"].format(e))
                return

            author = data.get("author", "Unknown")
            username = data.get("username", "unknown")
            author_link = f"<a href='https://tiktok.com/@{username}'>{author}</a>"

            if self.config["show_tiktok_info"]:
                caption_template = (
                    self.strings["tiktok_success_hd"] if quality == "hd" else self.strings["tiktok_success_sd"]
                )
                caption = caption_template.format(author_link, url)
            else:
                caption = (
                    self.strings["tiktok_success_minimal_hd"] if quality == "hd" else self.strings["tiktok_success_minimal_sd"]
                )

            await message.client.send_file(
                message.chat_id,
                video_path,
                caption=caption,
                reply_to=message.id,
                supports_streaming=True,
                parse_mode='HTML',
                video_note=False,
            )

    @loader.command(
        ru_doc="Скачать трек с Spotify.\nИспользование: .spot <ссылка>",
        en_doc="Download Spotify track.\nUsage: .spot <link>"
    )
    async def spotcmd(self, message: Message):
        """This command downloads music from Spotify."""        
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_url"])
            return

        user_url = args.strip()
        api_url = f"https://bj-tricks.serv00.net/Spotify-downloader-api/?url={user_url}"
      # await utils.answer(message, self.strings["fetching"])

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        await utils.answer(message, self.strings["api_error"].format(resp.status))
                        return
                    data = await resp.json()
            except Exception as e:
                await utils.answer(message, self.strings["api_exception"].format(e))
                return

        if not data.get("status"):
            await utils.answer(message, self.strings["api_fail"])
            return

        track_data = data.get("data", {})
        download_link = track_data.get("downloadLink")
        img_url = track_data.get("imgUrl")

        if not isinstance(download_link, str) or not isinstance(img_url, str):
            await utils.answer(
                message, 
                self.strings["invalid_data"].format(download_link, img_url)
            )
            return

        await utils.answer(message, self.strings["downloading"])

        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = os.path.join(tmpdir, "track.mp3")
            img_path = os.path.join(tmpdir, "cover.jpg")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(download_link) as resp:
                        if resp.status != 200:
                            await utils.answer(
                                message,
                                self.strings["download_error"].format(resp.status)
                            )
                            return
                        with open(mp3_path, "wb") as f:
                            f.write(await resp.read())

                    async with session.get(img_url) as resp:
                        if resp.status != 200:
                            await utils.answer(
                                message,
                                self.strings["image_error"].format(resp.status)
                            )
                            return
                        with open(img_path, "wb") as f:
                            f.write(await resp.read())
            except Exception as e:
                await utils.answer(message, self.strings["file_error"].format(e))
                return

            try:
                audio = MP3(mp3_path, ID3=ID3)
                try:
                    audio.add_tags()
                except Exception:
                    pass

                with open(img_path, 'rb') as albumart:
                    audio.tags.add(
                        APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=albumart.read()
                        )
                    )
                audio.save()
            except Exception as e:
                await utils.answer(message, self.strings["tag_error"].format(e))
                return

            caption = (
                self.strings["done_caption"].format(user_url) 
                if self.config["show_spotify_link"] 
                else self.strings["done_caption_minimal"]
            )

            await message.client.send_file(
                message.chat_id,
                mp3_path,
                caption=caption,
                reply_to=message.id,
                parse_mode='HTML',
                voice_note=False,
            )

    @loader.command(
        ru_doc="Скачать историю какого-то юзера.\nИспользование: .tgsload <username> <story_number>",
        en_doc="Download story of user.\nUsage: .tgsload <username> <story_number>")
    async def tgsloadcmd(self, message):
        """This command downloads a Telegram story."""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings("no_args_tgs"))
            return

        parts = args.strip().split()
        if len(parts) != 2:
            await utils.answer(message, self.strings("invalid_format_tgs"))
            return

        username = parts[0].lstrip('@')
        try:
            user_index = int(parts[1])
            if user_index <= 0:
                raise ValueError
            index = user_index - 1
        except ValueError:
            await utils.answer(message, self.strings("invalid_number_tgs"))
            return

        api_url = f"https://telegram-story.apis-bj-devs.workers.dev/?username={username}&action=archive"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    data = await resp.json()
        except Exception as e:
            await utils.answer(message, self.strings("api_error_tgs").format(error=e))
            return

        if not data.get("status") or "result" not in data or "stories" not in data["result"]:
            await utils.answer(message, self.strings("no_stories_tgs"))
            return

        stories = data["result"]["stories"]
        if not stories:
            await utils.answer(message, self.strings("no_stories_tgs"))
            return

        if index < 0 or index >= len(stories):
            await utils.answer(message, self.strings("invalid_index_tgs").format(max_index=len(stories)))
            return

        story = stories[index]
        url = story.get("url")
        caption = story.get("caption")

        if not url:
            await utils.answer(message, self.strings("no_url_tgs"))
            return

        downloading_message = await utils.answer(message, self.strings("downloading_tgs"))

        parsed_url = urlparse(url)
        file_extension = os.path.splitext(parsed_url.path)[1]
        if not file_extension:
            file_extension = '.mp4'  # Def NoExstension

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                        tmp_file.write(await resp.read())
                        tmp_file_path = tmp_file.name
        except Exception as e:
            await utils.answer(message, self.strings("download_error_tgs").format(error=e))
            return

        try:
            if self.config["show_caption"] and caption:
                if self.config["filter_links"] and caption:
                    caption = LINK_PATTERN.sub("", caption).strip()
                caption_text = self.strings("success_tgs").format(caption=caption)
            else:
                caption_text = self.strings("success_no_caption_tgs")

            await message.client.send_file(
                message.chat_id,
                tmp_file_path,
                caption=caption_text,
                reply_to=downloading_message.id
            )
        finally:
            os.remove(tmp_file_path)

    @loader.command(en_doc="Download YouTube video.\nUsage: .ytlh <link>.", ru_doc="Загрузить видео с YouTube.\nИспользование: .ytlh <link>.")
    async def ytlhcmd(self, message: Message):
        """Load YouTube video as link."""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings("yargs"))
            return

        if not await self._check_ffmpeg():
            await utils.answer(message, self.strings("ffmpeg_missing"))
            return

        m = await utils.answer(message, self.strings("yuploading"))
        API_URL = "https://gpt76.vercel.app/download"
        
        video_file, audio_file, output_file = None, None, None
        
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=2000)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                data = await self._fetch_json(session, API_URL, {"url": args})
                
                if not data.get("success"):
                    error_msg = data.get("error", "Unknown error")
                    await utils.answer(m, self.strings("yapi_error").format(error_msg))
                    return
                    
                medias = data.get("medias", [])
                if not medias:
                    await utils.answer(m, self.strings("yno_media"))
                    return
                
                video_streams = [
                    m for m in medias 
                    if m["type"] == "video" 
                    and not m.get("audioQuality")
                    and self._is_resolution_allowed(m)
                ]
                
                if not video_streams and not self.config["allow_high_res"]:
                    video_streams = [
                        m for m in medias 
                        if m["type"] == "video" 
                        and not m.get("audioQuality")
                    ]
                    video_streams = [v for v in video_streams if self._is_resolution_allowed(v)]
                    if not video_streams:
                        await utils.answer(m, self.strings("yno_allowed_res"))
                        return
                
                audio_streams = [m for m in medias if m["type"] == "audio"]
                
                if not video_streams or not audio_streams:
                    await utils.answer(m, self.strings("yno_media"))
                    return
                
                video_stream = max(
                    video_streams,
                    key=lambda x: (x.get("height", 0), x.get("bitrate", 0))
                )
                
                audio_stream = max(
                    audio_streams,
                    key=lambda x: x.get("bitrate", 0)
                )
                ytitle = data.get("title")
                yurl = data.get("url")
                title = "".join(c for c in data["title"] if c.isalnum() or c in " _-")
                video_file = f"{title}_video.{video_stream.get('ext', 'mp4')}"
                audio_file = f"{title}_audio.{audio_stream.get('ext', 'm4a')}"
                output_file = f"{title}.mp4"
                await self._download_file(session, video_stream["url"], video_file)
                await self._download_file(session, audio_stream["url"], audio_file)
                
                retcode = await self._merge_video_audio(video_file, audio_file, output_file)
                
                if retcode != 0:
                    log.error(f"FFmpeg back code err: {retcode}.")
                    await utils.answer(m, self.strings("ffmpeg_berror").format(retcode=retcode))
                    
                if not self.config["show_ytname"]:
                    await message.client.send_file(
                    message.peer_id,
                    output_file,
                    caption=self.strings("ysuccessm"),
                    reply_to=message.reply_to_msg_id
                    )
                else:
                    await message.client.send_file(
                    message.peer_id,
                    output_file,
                    caption=self.strings("ysuccess").format(ytitle=ytitle, yurl=yurl),
                    reply_to = message.reply_to_msg_id
                    )
                await m.delete()
        except ConnectionResetByPeer as e:
            log.error(f"YTLH error: {e} (104).")
            await utils.answer(m, self.strings["econnreset"])
    
        except Exception as e:
            log.error(f"YTLH error: {e}")
            await utils.answer(m, self.strings("yerror").format(str(e)))
        
        finally:
            for file in [video_file, audio_file, output_file]:
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                    except:
                        pass

#    @loader.command(en_doc="BETA WARNING.", ru_doc="BETA ПРЕДУПРЕЖДЕНИЕ.")
#    async def whybetavcmd(self, m: Message):
#        """BETA WARNING MESSAGE"""
#        await utils.answer(m, self.strings("whybeta"))
