__version__ = (1, 2, 1)
# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of Media-Downloader and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# meta developer: @KiyatsukaModules
# requires: aiohttp mutagen python-ffmpeg
# meta APIs Providers: https://t.me/BJ_devs, https://t.me/Teleservices_api
# scope: hikka_only
# scope: hikka_min 1.6.2
# changelog: 1.2.1 change-log: Improvements.

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
import sys
import inspect

log = logging.getLogger("Media-Downloader")

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
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Version: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> No updates available.",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Update available {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Changelog of the new version:</b>\n<i>{remote_changelog}</i>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>To update, use the command:</b></i> <code>{pref}dlm https://raw.githubusercontent.com/Walidname113/KModules/hikka/Media-Downloader.py</code>.",
        "_cls_doc": "👑 The best module designed to let you download the media you want without watermarks, service subscription, or author attribution in F/-HD.",
        "api_error_500": "<emoji document_id=5278578973595427038>🚫</emoji> API request error: {}. Try again. This should help."
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
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Версия: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> Обновлений нет.",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Доступно обновление {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Ченджлог новой версии:</b>\n<i>{remote_changelog}</i>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>Для обновления, используйте команду:</b></i> <code>{pref}dlm https://raw.githubusercontent.com/Walidname113/KModules/hikka/Media-Downloader.py</code>.",
        "_cls_doc": "👑 Лучший модуль, который поможет загрузить нужное вам медиа без водяного знака/подписки сервиса/автора в F/-HD.",
        "api_error_500": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при запросе к API. Статус: {}. Попробуйте снова. Это должно помочь."
    }

    strings_ua = {
        "name": "Media-Downloader",
        "no_args_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Вкажіть ім'я користувача та номер історії.",
        "invalid_format_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Формат: tgsload <ім'я_користувача> <номер_історії>`",
        "invalid_number_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Номер історії повинен бути додатним числом.",
        "api_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при запиті API: {error}",
        "no_stories_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Історії не знайдено.",
        "invalid_index_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Невірний номер історії. Доступний діапазон: 1 - {max_index}",
        "no_url_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> У вибраної історії відсутній URL.",
        "download_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при завантаженні файлу: {error}",
        "success_tgs": "<emoji document_id=5318760565902947324>✅</emoji> Історія успішно завантажена!\n<emoji document_id=6039451237743595514>📎</emoji> <b>Опис:</b> {caption}",
        "success_no_caption_tgs": "<emoji document_id=5318760565902947324>✅</emoji> Історія успішно завантажена!",
        "downloading_tgs": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую історію...",
        "cfg_show_caption_tgs": "Показувати опис у завантажених історіях.",
        "no_url": "<emoji document_id=5278578973595427038>🚫</emoji> Вкажи посилання на трек Spotify.",
        "fetching": "<emoji document_id=6030657343744644592>🔄</emoji> Отримую дані...",
        "api_error": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при запиті до API. Статус: {}",
        "api_exception": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при запиті до API: {}",
        "api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Не вдалося отримати дані треку.",
        "invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Некоректні дані від API.",
        "downloading": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую трек...",
        "download_error": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при завантаженні треку. Статус: {}",
        "image_error": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при завантаженні обкладинки. Статус: {}",
        "file_error": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при завантаженні файлів: {}",
        "tag_error": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при додаванні обкладинки: {}",
        "done_caption": "<emoji document_id=5318760565902947324>✅</emoji> Трек успішно завантажено!\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "done_caption_minimal": "<emoji document_id=5318760565902947324>✅</emoji> Трек успішно завантажено!",
        "no_tiktok_url": "<emoji document_id=5278578973595427038>🚫</emoji> Вкажи посилання на відео TikTok.",
        "tiktok_api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Не вдалося отримати дані відео.",
        "tiktok_invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Некоректні дані від TikTok API.",
        "tiktok_no_video": "<emoji document_id=5278578973595427038>🚫</emoji> Не знайдено підходящих відео для завантаження.",
        "downloading_hd": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую <b>HD</b> відео...",
        "downloading_sd": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую відео...",
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Відео успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Відео успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Відео успішно завантажено!",
        "tiktok_success_minimal_sd": "<emoji document_id=5318760565902947324>✅</emoji> Відео успішно завантажено!",
        "cfg_show_tiktok_info": "Показувати автора та посилання в TikTok.",
        "cfg_show_spotify_link": "Показувати посилання в Spotify.",
        "cfg_force_hd": "Завжди завантажувати відео в HD (якщо доступно).",
        "auto_update_ch": "Автоматично оновлювати модуль при нових версіях.",
        "cfg_filter_links": "Фільтрувати посилання в описах до історій при їх завантаженні.",
        "ffmpeg_missing": "<emoji document_id=5278578973595427038>🚫</emoji> FFmpeg не встановлено в системі. Встановіть <a href='https://t.me/hikka_talks/631886'>за посиланням</a>.",
        "yapi_error": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка API: <code>{}</code>.",
        "ysuccess": "<emoji document_id=4906943755644306322>🌐</emoji> <a href='{yurl}'>{ytitle}</a>\n\n<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Завантажено успішно!",
        "ysuccessm": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Завантажено успішно!",
        "yuploading": "<emoji document_id=5276220667182736079>⬇️</emoji> <b>[Може бути довго]</b> | Завантажую результат...",
        "yerror": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка: <code>{}</code>.",
        "yno_media": "<emoji document_id=5278578973595427038>🚫</emoji> Немає доступних медіа",
        "yargs": "<emoji document_id=5278578973595427038>🚫</emoji> Вкажи посилання на YouTube відео!",
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> Немає потоків у дозволеному розширенні! Щоб виправити, введіть: <code>{pref}fcfg Media-Downloader allow_high_res True</code> <b>(Не завжди допомагає)</b>.",
        "config_allow_high_res": "Дозволити завантаження >1080p60 | WARNING: Якщо ваш пристрій не підтримує більше ніж 1080p, немає сенсу дозволяти цю настройку.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>Попередження про BETA-версії!</b>\n\n<blockquote>Усі команди, які мають ініціали <b>BETA/ALPHA/TEST</b> — потенційно нестабільні. Це означає, що ці команди можуть часто викликати помилки або працювати неправильно, або взагалі не працювати, а іноді і зовсім <b>зламати роботу всього модуля</b>. Якщо ви цього не хочете, рекомендується більше не використовувати ці команди і чекати, поки вони будуть стабільно реалізовані. Бета-версії виходять тільки після тестування, тому помилки на кшталт повного зламу модуля <b>майже завжди виключені</b>, але гарантій немає.</blockquote>",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Сервер закрив з’єднання (104). Можливі рішення: Увімкнути блокування максимального якості завантаження відео в 1080p60 у конфігурації модуля (<code>allow_high_res</code>), якщо не допомагає — перевірити швидкість інтернету. Швидше за все, відео надто довге/якісне, через що займає забагато місця.",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg повернув помилку: <code>{retcode}</code>.",
        "show_ytdlh_vname": "Показувати назву відео при завантаженні з YouTube?",
        "rrs": "[Корисно] Канал з інформацією про модулі від розробника.",
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Версія: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> Оновлень немає.",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Доступне оновлення {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Ченджлог нової версії:</b>\n<i>{remote_changelog}</i>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>Для оновлення використайте команду:</b></i> <code>{pref}dlm https://raw.githubusercontent.com/Walidname113/KModules/hikka/Media-Downloader.py</code>.",
        "_cls_doc": "👑 Найкращий модуль, який допоможе завантажити потрібне вам медіа без водяного знака/підписки сервісу/автора в F/-HD.",
        "api_error_500": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при запиті до API. Статус: {}. Спробуйте ще раз. Це може допомогти."
    }
    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db        
        await self.request_join(
            "@KiyatsukaModules",
            self.strings['rrs'],
        )
    
    async def check_update_status(self):
        metadata_url = "https://raw.githubusercontent.com/Walidname113/KModules/hikka/Media-Downloader.py"

        try:
            module = sys.modules[__name__]
            sys_module = inspect.getmodule(module)
            local_version = ".".join(map(str, sys_module.__version__))
        except Exception:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(metadata_url) as resp:
                    if resp.status != 200:
                        return False
                    remote_text = await resp.text()
        except Exception:
            return False

        try:
            first_line = remote_text.splitlines()[0]
            if "__version__" not in first_line:
                return False
            remote_version = (
                first_line.split("=", 1)[1]
                .strip()
                .strip("()")
                .replace(",", "")
                .replace(" ", ".")
            )
        except Exception:
            return False

        return remote_version == local_version
                
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
        
    @loader.command(ru_doc="Скачать видео из TikTok.\nИспользование: .tikload <ссылка>.", en_doc="Download TikTok video.\nUsage: .tikload <link>.", ua_doc="Завантажити відео із TikTok.\nВикористання: .tikload <посилання>.")
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
                    if resp.status == 500:
                        await utils.answer(message, self.strings["api_error_500"].format(resp.status))
                    elif resp.status != 200:        
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

    @loader.command(ru_doc="Скачать трек с Spotify.\nИспользование: .spot <ссылка>.", en_doc="Download Spotify track.\nUsage: .spot <link>.", ua_doc="Завантажити трек із Spotify.\nВикористання: .spot <посилання>.")
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

    @loader.command(ru_doc="Скачать историю какого-то юзера.\nИспользование: .tgsload <юзернейм> <номер_истории>.", en_doc="Download story of user.\nUsage: .tgsload <username> <story_number>.", ua_doc="Завантажити історію користувача.\nВикористання: .tgsload <юзернейм> <номер_історії>.")
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

    @loader.command(en_doc="Download YouTube video.\nUsage: .ytlh <link>.", ru_doc="Загрузить видео с YouTube.\nИспользование: .ytlh <ссылка>.", ua_doc="Завантажити відео з YouTube.\nВикористання: .ytlh <посилання>.")
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
                    except (FileNotFoundError, FileExistsError):
                        pass

#    @loader.command(en_doc="BETA WARNING.", ru_doc="BETA ПРЕДУПРЕЖДЕНИЕ.", ua_doc="BETA ПОПЕРЕДЖЕННЯ.")
#    async def whybetavcmd(self, m: Message):
#        """BETA WARNING MESSAGE"""
#        await utils.answer(m, self.strings("whybeta"))

    @loader.command(en_doc="Check module updates.", ru_doc="Проверить обновления модуля.", ua_doc="Перевірити оновлення модуля.")
    async def updcheckcmd(self, message):
        """This command check module updates."""
        pref = self.get_prefix()
        
        metadata_url = "https://raw.githubusercontent.com/Walidname113/KModules/hikka/Media-Downloader.py"

        try:
            module = sys.modules[__name__]
            sys_module = inspect.getmodule(module)
            local_version = ".".join(map(str, sys_module.__version__))
        except Exception:
            log.error("The function failed to get the local version of the module.")
            await utils.answer(message, "<emoji document_id=5278578973595427038>🚫</emoji> <b>ERROR. More info in logs.</b>")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(metadata_url) as resp:
                    if resp.status != 200:
                        log.error(f"Github return {resp.status} code, although 200 was expected.")
                        await utils.answer(message, "<emoji document_id=5278578973595427038>🚫</emoji> <b>ERROR. More info in logs.</b>")
                        return
                    remote_text = await resp.text()
        except Exception:
            log.error("Failed to connect on GitHub.")
            await utils.answer(message, "<emoji document_id=5278578973595427038>🚫</emoji> <b>ERROR. More info in logs.</b>")
            return

        remote_lines = remote_text.splitlines()

        try:
            first_line = remote_lines[0]
            remote_version = (
                first_line.split("=", 1)[1]
                .strip()
                .strip("()")
                .replace(",", "")
                .replace(" ", ".")
            )
        except Exception:
            log.error("Failed to fetch remote version.")
            await utils.answer(message, "<emoji document_id=5278578973595427038>🚫</emoji> <b>ERROR. More info in logs.</b>")
            return

        remote_changelog = next(
            (line.split(":", 1)[1].strip() for line in remote_lines if line.lower().strip().startswith("# changelog:")),
            "—"
        )

        if remote_version == local_version:
            await utils.answer(message, self.strings("nupdm").format(local_version=local_version))
        else:
            await utils.answer(message, self.strings("updm").format(
                local_version=local_version,
                remote_version=remote_version,
                remote_changelog=remote_changelog,
                pref=pref
            ))
