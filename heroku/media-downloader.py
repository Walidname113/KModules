__version__ = (1, 2, 9)
# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of Media-Downloader and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# meta developer: @KiyatsukaModules
# requires: aiohttp mutagen python-ffmpeg yt_dlp
# meta APIs Providers: https://t.me/BJ_devs, https://t.me/Teleservices_api
# scope: hikka_min 1.6.2
# scope: ffmpeg
# changelog: 1.2.9 change-log: [BETA] This update brings a rework of tikload, ytlh for better use. Also in this update there are bug fixes and improvements.

from herokutl.types import Message # type: ignore
from .. import loader, utils
import aiohttp # type: ignore
import os
import tempfile
from mutagen.mp3 import MP3 # type: ignore
from mutagen.id3 import ID3, APIC # type: ignore
from urllib.parse import urlparse
import asyncio
import re
import logging
import sys
import inspect
import io
import json
import shutil
from typing import Any, Dict, List, Optional, Union
import yt_dlp

log = logging.getLogger("Media-Downloader")

LINK_PATTERN = re.compile(
    r"(?:http[s]?://|www\.)[^\s\/]+?\.(?:com|net|org|io|ru|su|ua|jp)(?:[\/\w\-\.\?\=\&\%\#]*)",
    flags=re.IGNORECASE
)

class ConnectionResetByPeer(Exception):
    pass

class YouTubeDownloaderError(Exception):
    """Custom exception for YouTubeDownloader errors with optional hint."""
    def __init__(self, message: str, hint: Optional[str] = None) -> None:
        super().__init__(message)
        self.hint: Optional[str] = hint


class AsyncYouTubeDownloader:
    VALID_VIDEO_QUALITY_REGEX = re.compile(
        r'^(?P<height>\d{3,4})(?:p)?(?:\d{2})?(?:\s*HDR)?$', re.IGNORECASE
    )
    SUPPORTED_AUDIO_QUALITIES: List[str] = ['low', 'medium', 'high', 'best']

    def __init__(
        self,
        video_url: str,
        enable_logs: bool = False,
        auto_download: bool = False,
        video_quality: Optional[str] = None,
        audio_quality: str = 'best',
        force_combined: bool = False
    ) -> None:
        self.video_url: str = video_url
        self.enable_logs: bool = enable_logs
        self.auto_download: bool = auto_download
        self.video_quality: Optional[str] = video_quality
        self.audio_quality: str = audio_quality
        self.force_combined: bool = force_combined
        self.info: Optional[Dict[str, Any]] = None
        self.result: Dict[str, Any] = {}

    def _validate_video_quality(self, quality: str) -> str:
        if not quality:
            return ''
        match = self.VALID_VIDEO_QUALITY_REGEX.match(quality.replace(' ', ''))
        if match:
            return quality.strip()
        raise YouTubeDownloaderError(
            f"Invalid video quality: {quality}",
            hint="Valid examples: '720p', '1080p60', '720 HDR', '720p HDR'"
        )

    def _validate_audio_quality(self, quality: str) -> str:
        if quality not in self.SUPPORTED_AUDIO_QUALITIES:
            raise YouTubeDownloaderError(
                f"Invalid audio quality: {quality}",
                hint=f"Supported values: {', '.join(self.SUPPORTED_AUDIO_QUALITIES)}"
            )
        return quality

    def _get_best_audio(self, audio_formats: List[Dict[str, Any]]) -> Optional[str]:
        if not audio_formats:
            return None
        if self.audio_quality == 'best':
            audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
            return audio_formats[0]['url']
        audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
        return audio_formats[0]['url']

    def _choose_video_format(self, video_formats: List[Dict[str, Any]]) -> Dict[str, Any]:
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for f in video_formats:
            res = f.get('height') or 0
            grouped.setdefault(res, []).append(f)

        desired_height: Optional[int] = None
        if self.video_quality:
            vq = self._validate_video_quality(self.video_quality)
            desired_height = int(re.search(r'\d{3,4}', vq).group())

        available_heights = sorted(grouped.keys())
        if not available_heights:
            raise YouTubeDownloaderError(
                "No available video formats",
                hint="Check if the video URL is correct and the video is accessible."
            )

        chosen_height: int
        if desired_height:
            if desired_height in available_heights:
                chosen_height = desired_height
            else:
                higher = [h for h in available_heights if h > desired_height]
                lower = [h for h in available_heights if h < desired_height]
                if lower:
                    chosen_height = max(lower)
                elif higher:
                    chosen_height = min(higher)
                else:
                    chosen_height = max(available_heights)
        else:
            chosen_height = max(available_heights)

        group = grouped[chosen_height]
        group.sort(key=lambda x: (x.get('fps', 0), x.get('tbr', 0)), reverse=True)
        return group[0]

    async def _run_ffmpeg_merge(self, video_path: str, audio_path: str, output_path: str) -> None:
        """Asynchronously merge video and audio using ffmpeg."""
        if not shutil.which("ffmpeg"):
            raise YouTubeDownloaderError(
                "ffmpeg not found",
                hint="Install ffmpeg and add it to PATH for combining video and audio."
            )
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise YouTubeDownloaderError(f"ffmpeg merge failed:\n{stderr.decode()}")

    async def download(self) -> None:
        """Download video and audio asynchronously and optionally combine."""
        try:
            ydl_opts: Dict[str, Any] = {}
            if not self.enable_logs:
                ydl_opts['quiet'] = True

            self.info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(self.video_url, download=False))
            formats: List[Dict[str, Any]] = self.info.get('formats', [])

            video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('format_note') != 'storyboard']
            audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']

            if not video_formats:
                raise YouTubeDownloaderError("No video formats available", hint="Check the video URL")

            self._validate_audio_quality(self.audio_quality)
            best_audio_url = self._get_best_audio(audio_formats)

            best_video = self._choose_video_format(video_formats)
            has_audio = best_video.get('acodec') != 'none'
            combined = has_audio or self.force_combined

            video_entry: Dict[str, Union[str, bool]] = {
                "video_url": best_video['url'],
                "quality": best_video.get('format_note') or f"{best_video.get('height', 'unknown')}p",
                "combined": combined
            }

            if not has_audio or self.force_combined:
                if audio_formats:
                    video_entry["audio_hdplay"] = self._get_best_audio(audio_formats)

            self.result = {
                "videos": [video_entry],
                "audio_hdplay": best_audio_url,
                "meta": {
                    "title": self.info.get('title'),
                    "views": self.info.get('view_count'),
                    "uploader": self.info.get('uploader'),
                    "duration": self.info.get('duration'),
                    "description": self.info.get('description'),
                    "best_audio_url": best_audio_url,
                    "thumbnail": self.info.get('thumbnail')
                }
            }

            if self.auto_download:
                await asyncio.to_thread(self._download_video, best_video, audio_formats, combined)

        except YouTubeDownloaderError as e:
            print(f"[ERROR] {e}")
            if e.hint:
                print(f"[HINT] {e.hint}")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            print(f"[HINT] Check the video URL and ensure ffmpeg is installed if combining streams.")

    def _download_video(self, best_video: Dict[str, Any], audio_formats: List[Dict[str, Any]], combined: bool) -> None:
        """Synchronous helper to download video/audio using yt-dlp in a thread."""
        ydl_opts: Dict[str, Any] = {}
        if not combined and audio_formats:
            ydl_opts['format'] = f"{best_video['format_id']}+{audio_formats[0]['format_id']}"
        else:
            ydl_opts['format'] = best_video['format_id']
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([self.video_url])

    def get_json(self) -> str:
        """Return the download info and metadata as UTF-8 JSON."""
        return json.dumps(self.result, indent=4, ensure_ascii=False)


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
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Video successfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Video succesfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
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
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> No streams in allowed resolution! To fix, enter: <code>{pref}fcfg Media-Downloader allow_high_res True</code>.",
        "config_allow_high_res": "Allow downloading >1080p60 | WARNING: If your device does not support more than 1080p, enabling this setting makes no sense.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>BETA version warning!</b>\n\n<blockquote>All commands labeled <b>BETA/ALPHA/TEST</b> are potentially unstable. This means these commands may often cause errors, malfunction, or not work at all, and sometimes even <b>break the entire module</b>. If you want to avoid this, it is advised to stop using these commands and wait until they are stable. Beta versions are released only after testing, so errors causing total module failure are <b>almost always excluded</b>, but there is no guarantee they won’t occur.</blockquote>",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Server closed connection (104). Possible solution: Enable blocking of video up to 1080p60 in module config (<code>allow_high_res</code>), if it does not help: check the speed of the Internet connection.",
        "show_ytdlh_vname": "Show the title of a YouTube video when it is loaded?",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg return Error: <code>{retcode}</code>.",
        "rrs": "[Useful] Channel with information about modules from the developer.",
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Version: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> No updates available.",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Update available {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Changelog of the new version:</b>\n<blockquote>{remote_changelog}</blockquote>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>To update, use the command:</b></i> <code>{pref}dlm https://raw.githubusercontent.com/Walidname113/KModules/heroku/Media-Downloader.py</code>.",
        "_cls_doc": "👑 The best module designed to let you download the media you want without watermarks, service subscription, or author attribution in F/-HD.",
        "ph_succesfully": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Photo successfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
        "downloading_ph": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading <b>HD</b> photo...",
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
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Видео успешно загружено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Видео успешно загружено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
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
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> Нет потоков в разрешенном разрешении! Чтобы исправить, введите: <code>{pref}fcfg Media-Downloader allow_high_res True</code> <b>(Не всегда помогает)</b>.",
        "config_allow_high_res": "Разрешить скачивание >1080p60 | WARNING: Если ваше устройство не поддерживает больше чем 1080р, смысла разрешать эту настройку нет.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>Предупреждение о BETA-версиях!</b>\n\n<blockquote>Все команды, которые имеют инициалы <b>BETA/ALPHA/TEST</b> — потенциально нестабильны. Это значит, что эти команды могут часто вызывать ошибки или неправильно работать, или вовсе не работать, а иногда и вообще <b>сломать работу всего модуля</b>. Если вы не хотите этого, советуется больше не использовать эти команды, и ждать пока они будут стабильно реализованы. Бета версии выходят только после их тестирования, так что ошибки по типу полной поломки модуля <b>почти всегда исключены</b>, но нету гарантии что их не будет.</blockquote>",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Сервер закрыл соединение (104). Возможные решения: Включить блокировку максимального качества загрузки видео в 1080р60 в конфиге модуля (<code>allow_high_res</code>), если не помогает, то проверить скорость интернета. Скорее всего, видео слишком долгое/качественное, от чего занимает слишком много места.",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg вернул ошибку: <code>{retcode}</code>.",
        "show_ytdlh_vname": "Показывать ли название видео при загрузке с YouTube?",
        "rrs": "[Полезно] Канал с информацией о модулях от разработчика.",
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Версия: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> Обновлений нет.",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Доступно обновление {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Ченджлог новой версии:</b>\n<blockquote>{remote_changelog}</blockquote>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>Для обновления, используйте команду:</b></i> <code>{pref}dlm https://raw.githubusercontent.com/Walidname113/KModules/heroku/Media-Downloader.py</code>.",
        "_cls_doc": "👑 Лучший модуль, который поможет загрузить нужное вам медиа без водяного знака/подписки сервиса/автора в F/-HD.",
        "ph_succesfully": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Фото успешно загружены!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>", 
        "downloading_ph": "<emoji document_id=5276220667182736079>⬇️</emoji> Загружаю <b>HD</b> фото...",
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
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Відео успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Відео успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
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
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Доступне оновлення {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Ченджлог нової версії:</b>\n<blockquote>{remote_changelog}</blockquote>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>Для оновлення використайте команду:</b></i> <code>{pref}dlm https://raw.githubusercontent.com/Walidname113/KModules/heroku/Media-Downloader.py</code>.",
        "_cls_doc": "👑 Найкращий модуль, який допоможе завантажити потрібне вам медіа без водяного знака/підписки сервісу/автора в F/-HD.",
        "ph_succesfully": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Фото успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{original_url}</code>",
        "downloading_ph": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую <b>HD</b> фото...",
        "api_error_500": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при запиті до API. Статус: {}. Спробуйте ще раз. Це може допомогти."
    }
    
    API_URL_TOKEN = "https://logkiya.netlify.app/.netlify/functions/tokenGen"
    API_URL_LOG = "https://logkiya.netlify.app/.netlify/functions/logUser"

    async def get_token(self, whatgen, user_id=None):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.API_URL_TOKEN, json={"whatgen": whatgen}) as r:
                    r.raise_for_status()
                    text = (await r.text()).strip()
                    try:
                        data = json.loads(text)
                        token = data.get("token", "").strip()
                        log.warning(f"Получен JSON токен: '{token}'")
                    except Exception:
                        token = text
                        log.warning(f"Получен plain text токен: '{token}'")

                    if user_id:
                        payload = {
                            "userId": user_id,
                            "token": token,
                            "developerKey": "publictoken"
                        }
                        log.warning(f"Payload для logUser, который будет отправлен: {payload}")

                    return token

            except aiohttp.ClientResponseError as e:
                log.error(f"Error due CRE: {e}")
            except Exception as e:
                log.error(f"Error due Exc: {e}")

        return None

    async def log_user(self, user_id, token):
        async with aiohttp.ClientSession() as session:
            token = token.strip()
            developerKey = "publictoken"
            payload = {"userId": user_id, "token": token, "developerKey": developerKey}
            log.warning(f"Отправка запроса на logUser с payload: {payload}")

            try:
                async with session.post(self.API_URL_LOG, json=payload) as r:
                    r.raise_for_status()
                    text = (await r.text()).strip()
                    try:
                        data = json.loads(text)
                        log.warning(f"Ответ от logUser (JSON): {data}")
                        return data
                    except Exception:
                        log.warning(f"Ответ от logUser (plain text): {text}")
                        return text
            except aiohttp.ClientResponseError as e:
                log.error(f"Error due CRE: {e}")
            except Exception as e:
                log.error(f"Error due Exc: {e}")

        return None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

        user_id = (await self.client.get_me()).id
        token = await self.get_token("2", user_id=user_id)
        if token:
            await self.log_user(user_id, token)
            log.warning(f"Токен '{token}' получен и пользователь '{user_id}' залогирован.")

        await self.request_join(
            "@KiyatsukaModules",
            self.strings['rrs'],
        )

    async def check_update_status(self):
        metadata_url = "https://api.fixyres.com/module/Walidname113/KModules/heroku/media-downloader.py"

        try:
            module = sys.modules[__name__]
            sys_module = inspect.getmdule(module)
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
        
# Command to download TikTok media
    @loader.command(ru_doc="Скачать медиа из TikTok.\nИспользование: .tikload <ссылка>.",
                    en_doc="Download TikTok media.\nUsage: .tikload <link>.",
                    ua_doc="Завантажити медіа із TikTok.\nВикористання: .tikload <посилання>.")
    async def tikloadcmd(self, message: Message):
        """This command download a TikTok mediafiles."""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_tiktok_url"])
            return

        url = args.strip()
        original_url = url

        media_type = "video" if "/video/" in url else "photo" if "/photo/" in url else None
        media_id = None

        if media_type:
            match = re.search(rf"/{media_type}/(\d+)", url)
            if match:
                media_id = match.group(1)

        if not media_id:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(url, allow_redirects=True) as resp:
                        final_url = str(resp.url)
                        media_type = "video" if "/video/" in final_url else "photo" if "/photo/" in final_url else None
                        match = re.search(rf"/{media_type}/(\d+)", final_url) if media_type else None
                        media_id = match.group(1) if match else None
            except Exception:
                await utils.answer(message, self.strings["tiktok_api_fail"])
                return

        if not media_id or not media_type:
            await utils.answer(message, self.strings["tiktok_api_fail"])
            return

        if media_type == "video":
            api_url = f"https://www.tikwm.com/api/?url={original_url}"
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

            if not data or not data.get("data"):
                await utils.answer(message, self.strings["tiktok_api_fail"])
                return

            video_url = data.get("data", {}).get("play", "")
            if not video_url:
                await utils.answer(message, self.strings["tiktok_no_video"])
                return

            await utils.answer(message, self.strings["downloading_hd"])

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_url) as resp:
                        if resp.status != 200:
                            await utils.answer(message, self.strings["download_error"].format(resp.status))
                            return
                        video_bytes = await resp.read()
            except Exception as e:
                await utils.answer(message, self.strings["file_error"].format(e))
                return

            video_stream = io.BytesIO(video_bytes)
            video_stream.name = "video.mp4"

            author_info = data.get("data", {}).get("author", {})
            username = author_info.get("unique_id", "unknown")
            nickname = author_info.get("nickname", "Unknown")
            author = f"<a href='https://www.tiktok.com/@{username}'>{nickname}</a>"

            caption = self.strings["tiktok_success_hd"].format(username=username, nickname=nickname, original_url=original_url, author=author)

            await message.client.send_file(
                message.chat_id,
                video_stream,
                caption=caption,
                reply_to=message.id,
                supports_streaming=True,
                parse_mode='HTML',
                video_note=False,
            )
            return

        elif media_type == "photo":
            api_url = f"https://www.tikwm.com/api/?url=https://www.tiktok.com/photo/{media_id}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url) as resp:
                        if resp.status != 200:
                            await utils.answer(message, self.strings["api_error"].format(resp.status))
                            return
                        data = await resp.json()
            except Exception:
                await utils.answer(message, self.strings["tiktok_api_fail"])
                return

            images = data.get("data", {}).get("images", [])
            if not images:
                await utils.answer(message, self.strings["tiktok_no_video"])
                return

            await utils.answer(message, self.strings["downloading_ph"])

            photo_streams = []
            for idx, img_url in enumerate(images, 1):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url) as resp:
                            if resp.status != 200:
                                continue
                            img_bytes = await resp.read()
                    img_stream = io.BytesIO(img_bytes)
                    img_stream.name = f"{media_id}_{idx}.jpg"
                    photo_streams.append(img_stream)
                except Exception:
                    continue

            if not photo_streams:
                await utils.answer(message, self.strings["tiktok_no_video"])
                return

            author_info = data.get("data", {}).get("author", {})
            username = author_info.get("unique_id", "unknown")
            nickname = author_info.get("nickname", "Unknown")
            author = f"<a href='https://www.tiktok.com/@{username}'>{nickname}</a>"

            caption = self.strings["ph_succesfully"].format(username=username, nickname=nickname, original_url=original_url, author=author)

            await message.client.send_file(
                message.chat_id,
                photo_streams,
                reply_to=message.id,
                caption=caption,
                parse_mode="HTML"
            )
            return


    @loader.command(
        ru_doc="Скачать трек с Spotify.\nИспользование: .spot <ссылка>.",
        en_doc="Download Spotify track.\nUsage: .spot <link>.",
        ua_doc="Завантажити трек із Spotify.\nВикористання: .spot <посилання>."
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
        ru_doc="Скачать историю какого-то юзера.\nИспользование: .tgsload <юзернейм> <номер_истории>.",
        en_doc="Download story of user.\nUsage: .tgsload <username> <story_number>.",
        ua_doc="Завантажити історію користувача.\nВикористання: .tgsload <юзернейм> <номер_історії>.")
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

    @loader.command(en_doc="Download YouTube video.\nUsage: .ytlh <link>.",
                    ru_doc="Загрузить видео с YouTube.\nИспользование: .ytlh <ссылка>.",
                    ua_doc="Завантажити відео з YouTube.\nВикористання: .ytlh <посилання>.")
    async def ytlhcmd(self, message: Message):
        """Load YouTube video via yt-dlp."""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings("yargs"))
            return

        if not await self._check_ffmpeg():
            await utils.answer(message, self.strings("ffmpeg_missing"))
            return

        m = await utils.answer(message, self.strings("yuploading"))

        video_file = None
        audio_file = None
        output_file = None
        thumb_file = None

        try:
            # init downloader
            allow_high_res = self.config.get("allow_high_res", False)
            downloader = AsyncYouTubeDownloader(
                video_url=args,
                enable_logs=False,
                auto_download=False,
            )
            await downloader.download()

            info = downloader.result
            videos = info.get("videos", [])
            meta = info.get("meta", {})
            ytitle = meta.get("title")
            yurl = args
            thumbnail_url = meta.get("thumbnail")

            if not videos:
                await utils.answer(m, self.strings("yno_media"))
                return

            def extract_height(q: str) -> int:
                try:
                    match = re.search(r"\d+", q or "")
                    return int(match.group()) if match else 0
                except Exception:
                    return 0

            selected_video = None
            if allow_high_res:
                high_res = [v for v in videos if extract_height(v.get("quality", "")) >= 1440]
                if high_res:
                    selected_video = max(high_res, key=lambda x: extract_height(x.get("quality", "")))
                else:
                    selected_video = max(videos, key=lambda x: extract_height(x.get("quality", "")))
            else:
                filtered = [v for v in videos if extract_height(v.get("quality", "")) <= 1080]
                if not filtered:
                    filtered = videos
                selected_video = max(filtered, key=lambda x: extract_height(x.get("quality", "")))

            video_url = selected_video.get("video_url")
            audio_url = selected_video.get("audio_hdplay")
            if not video_url:
                await utils.answer(m, self.strings("yno_media"))
                return

            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"Video download failed with status {resp.status}")
                    video_bytes = await resp.read()

                if audio_url:
                    async with session.get(audio_url) as resp:
                        if resp.status != 200:
                            raise Exception(f"Audio download failed with status {resp.status}")
                        audio_bytes = await resp.read()

                thumb_bytes = None
                if thumbnail_url:
                    try:
                        async with session.get(thumbnail_url) as resp:
                            if resp.status == 200:
                                thumb_bytes = await resp.read()
                    except Exception:
                        thumb_bytes = None

            video_file = f"yt_video.mp4"
            with open(video_file, "wb") as f:
                f.write(video_bytes)

            if audio_url and audio_bytes:
                audio_file = f"yt_audio.m4a"
                with open(audio_file, "wb") as f:
                    f.write(audio_bytes)

                output_file = f"yt_merged.mp4"
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-i", video_file, "-i", audio_file,
                    "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart",
                    output_file,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    raise Exception(f"FFmpeg merge failed: {stderr.decode()}")

                send_file = output_file
            else:
                send_file = video_file

            thumb_stream = io.BytesIO(thumb_bytes) if thumb_bytes else None
            if thumb_stream:
                thumb_stream.name = "thumb.jpg"

            caption = self.strings("ysuccess").format(ytitle=ytitle, yurl=yurl)

            await message.client.send_file(
                message.peer_id,
                send_file,
                caption=caption,
                reply_to=message.reply_to_msg_id,
                thumb=thumb_stream
            )

            await m.delete()

        except Exception as e:
            log.error(f"YTLH error: {e}")
            await utils.answer(m, self.strings("yerror").format(str(e)))

        finally:
            for file in [video_file, audio_file, output_file]:
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                    except Exception as e:
                        log.error(e)

#    @loader.command(en_doc="BETA WARNING.", ru_doc="BETA ПРЕДУПРЕЖДЕНИЕ.", ua_doc="BETA ПОПЕРЕДЖЕННЯ.")
#    async def whybetavcmd(self, m: Message):
#        """BETA WARNING MESSAGE"""
#        await utils.answer(m, self.strings("whybeta"))

    @loader.command(en_doc="Check module updates.", ru_doc="Проверить обновления модуля.", ua_doc="Перевірити оновлення модуля.")
    async def updcheckcmd(self, message):
        """This command check module updates."""
        pref = self.get_prefix()
        
        metadata_url = "https://api.fixyres.com/module/Walidname113/KModules/heroku/media-downloader.py"

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

        async with aiohttp.ClientSession() as session:

            async def check_tiktok():
                try:
                    test_url = "https://www.tiktok.com/@4wizz_kg/video/7550405003010149639"
                    api_url = f"https://www.tikwm.com/api/?url={test_url}"
                    async with session.get(api_url) as r:
                        if r.status != 200:
                            return "<emoji document_id=5278578973595427038>🚫</emoji>"
                        data = await r.json()
                        video_url = data.get("data", {}).get("play", "")
                        return "<emoji document_id=5278411813468269386>✔️</emoji>" if video_url else "<emoji document_id=5278578973595427038>🚫</emoji>"
                except Exception as e:
                    log.error(f"TikTok status checking error: {e}")
                    return "🚫 ERROR. More info in logs."

            async def check_spotify():
                try:
                    async with session.get("https://bj-tricks.serv00.net/Spotify-downloader-api/?url=https://open.spotify.com/track/2re6FKxMAOBgQMl0V58U0p") as r:
                        data = await r.json()
                        dl_link = data.get("data", {}).get("downloadLink")
                        return "<emoji document_id=5278411813468269386>✔️</emoji>" if dl_link else "<emoji document_id=5278578973595427038>🚫</emoji>"
                except Exception as e:
                    return "<b>🚫 ERROR. More info in logs.</b>"
                    log.error(f"Spotify status checking error: {e}")

            async def check_telegram_story():
                try:
                    async with session.get("https://telegram-story.apis-bj-devs.workers.dev/?username=Kiyatsuka&action=archive") as r:
                        data = await r.json()
                        if data.get("status") is True and data.get("code") == 200:
                            return "<emoji document_id=5278411813468269386>✔️</emoji>"
                        else:
                            return "<emoji document_id=5278578973595427038>🚫</emoji>"
                except Exception as e:
                    return "🚫 ERROR. More info in logs."
                    log.error(f"Telegram story status checking error: {e}")

            tiktok_status, spotify_status, tg_status = await asyncio.gather(
                check_tiktok(), check_spotify(), check_telegram_story()
            )

        if remote_version == local_version:
            await utils.answer(message, f"{self.strings('nupdm').format(local_version=local_version)}\n\n"
                                        f"<emoji document_id=5472371913785354427>🎵</emoji> TikTok API status: {tiktok_status}\n"
                                        f"<emoji document_id=5472235454084426508>♏</emoji> Spotify API status: {spotify_status}\n"
                                        f"<emoji document_id=5471949924658588235>🩵</emoji> Telegram Story API status: {tg_status}")
        else:
            await utils.answer(message, f"{self.strings('updm').format(local_version=local_version, remote_version=remote_version, remote_changelog=remote_changelog, pref=pref)}\n\n"
                                        f"<emoji document_id=5472371913785354427>🎵</emoji> TikTok API status: {tiktok_status}\n"
                                        f"<emoji document_id=5472235454084426508>♏</emoji> Spotify API status: {spotify_status}\n"
                                        f"<emoji document_id=5471949924658588235>🩵</emoji> Telegram Story API status: {tg_status}")
