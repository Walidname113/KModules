__version__ = (1, 3, 6)
# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of Media-Downloader and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# meta developer: @KiyatsukaModules
# requires: aiohttp mutagen python-ffmpeg yt_dlp instaloader
# meta APIs Providers: https://t.me/BJ_devs
# scope: hikka_min 1.6.2
# scope: ffmpeg
# changelog: 1.3.6 change-log: Improvements to Youtube downloader.

from herokutl.types import Message # type: ignore
from .. import loader, utils
import aiohttp # type: ignore
import os
import tempfile
from mutagen.mp3 import MP3 # type: ignore
from mutagen.id3 import ID3, APIC # type: ignore
from urllib.parse import urlparse, urlunparse
import asyncio
import re
import logging
import sys
import inspect
import io
import json
import shutil
from typing import Any, Dict, List, Optional, Union
import yt_dlp # type: ignore
import zipfile
import instaloader # type: ignore
from instaloader import Instaloader, Post # type: ignore
from pathlib import Path
import subprocess

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
                    "uploader_id": self.info.get('uploader_id'),
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

class InstaReelMeta:
    def __init__(self):
        self.L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )

    def get_author(self, url: str) -> str:
        shortcode = url.strip("/").split("/")[-1]
        post = instaloader.Post.from_shortcode(self.L.context, shortcode)
        profile = post.owner_profile

        data = {
            "author": {
                "username": profile.username,
                "full_name": profile.full_name
            }
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

def clean_social_link(url: str) -> str:
    parsed = urlparse(url)
    clean_url = parsed._replace(query="", fragment="")
    return urlunparse(clean_url)

class SpotifyDownloader:
    """
    SpotifyDownloader downloads Spotify tracks via a direct-download API.
    It automatically converts a Spotify track URL into a downloadable mp3.
    """

    def __init__(
        self,
        logging_enabled: bool = False,
        max_log_level: Optional[int] = logging.ERROR,
        log_format: Optional[str] = None
    ) -> None:
        self.logging_enabled: bool = logging_enabled or (max_log_level is not None)
        self.max_log_level: Optional[int] = max_log_level
        self.logger: Optional[logging.Logger] = None
        if self.logging_enabled:
            self._init_default_logger(log_format)

    def _init_default_logger(self, log_format: Optional[str] = None) -> None:
        logger: logging.Logger = logging.getLogger("SpotifyDownloader")
        if self.max_log_level is not None:
            logger.setLevel(self.max_log_level)
        handler: logging.StreamHandler = logging.StreamHandler()
        fmt: str = log_format or "%(levelname)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.handlers = []
        logger.addHandler(handler)
        self.logger = logger

    def set_logger(self, logger: logging.Logger) -> None:
        self.logger = logger

    async def download(
        self,
        spotify_url: str,
        outfile: Optional[Union[str, Path]] = "track.mp3",
        temporary: bool = False
    ) -> Optional[str]:
        """
        Download a Spotify track by converting the Spotify URL through the API.
        """
        if outfile is None and temporary:
            tmp: tempfile.NamedTemporaryFile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            outfile = tmp.name
            tmp.close()

        if self.logger:
            self.logger.info(f"Converting Spotify URL: {spotify_url}")

        api_url = f"https://spotmp3.app/api/direct-download?url={spotify_url}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        if self.logger:
                            self.logger.error(f"HTTP error from API: {resp.status}")
                        return None

                    path: Path = Path(outfile)
                    with open(path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 1024):
                            if chunk:
                                f.write(chunk)

            if self.logger:
                self.logger.info(f"Download completed: {outfile}")
            return str(outfile)

        except aiohttp.ClientError as e:
            if self.logger:
                self.logger.warning(f"Client error: {e}")
            return None

        except Exception as e:
            if self.logger:
                self.logger.error(f"Critical error: {e}")
            return None

def _parse_version(v: str):
    """Return tuple for comparison: (major, minor, patch, is_nightly, nightly_num)"""
    if not v:
        return (0, 0, 0, False, 0)
    v = v.strip()
    is_nightly = "nightly" in v
    nums = re.findall(r"\d+", v)
    major, minor, patch, *rest = (list(map(int, nums[:3])) + [0, 0, 0])[:3]
    nightly_num = int(nums[-1]) if is_nightly and nums else 0
    return (major, minor, patch, is_nightly, nightly_num)


async def ensure_nightly(enable_logs: bool = True):
    if enable_logs:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
        log = logging.info
        log_error = logging.error
    else:
        log = lambda *a, **k: None
        log_error = lambda *a, **k: None

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "show", "yt-dlp",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    current_ver = None
    for line in out.decode().splitlines():
        if line.startswith("Version:"):
            current_ver = line.split(":", 1)[1].strip()
    log(f"Current installed yt-dlp version: {current_ver or 'not installed'}")

    proc2 = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "index", "versions", "yt-dlp",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    out2, err2 = await proc2.communicate()
    text = out2.decode()

    nightly_versions = [v.strip(",") for v in text.split() if "nightly" in v.lower()]
    if not nightly_versions:
        log("No nightly versions found on PyPI")
        return

    latest_ver = sorted(nightly_versions, key=_parse_version, reverse=True)[0]
    log(f"Latest nightly version on PyPI: {latest_ver}")

    if current_ver is None or _parse_version(latest_ver) > _parse_version(current_ver):
        log("Installing latest nightly version...")
        proc3 = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "--pre", "-U", "yt-dlp-nightly",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        out3, err3 = await proc3.communicate()
        if proc3.returncode == 0:
            log("Nightly version installed successfully")
        else:
            log_error(f"Failed to install nightly version: {err3.decode().strip()}")
    else:
        log("Installed version is up-to-date; no update needed")

@loader.tds
class MediaDownloaderMod(loader.Module):
    """👑 The best module designed to let you download the media you want without watermarks, service subscription, or author attribution in F/-HD."""

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
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Video successfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Video succesfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Video succesfully downloaded!",
        "tiktok_success_minimal_sd": "<emoji document_id=5318760565902947324>✅</emoji> Video succesfully downloaded!",
        "cfg_show_tiktok_info": "Show author and link for TikTok message caption?",
        "cfg_show_spotify_link": "Show link for Spotify caption message after downloading track?",
        "cfg_force_hd": "Always download HD from TikTok (if available)?",
        "auto_update_ch": "Autoupdate module when new versions?",
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
        "cfg_show_caption_tgs": "Display captions for downloaded stories?",
        "cfg_filter_links": "Filter out links in story captions?",
        "ffmpeg_missing": "<emoji document_id=5278578973595427038>🚫</emoji> FFmpeg is not installed on the system. Install it <a href='https://t.me/hikka_talks/631886'>via this link</a>.",
        "yapi_error": "<emoji document_id=5278578973595427038>🚫</emoji> API error: <code>{}</code>.",
        "ysuccess": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Download successful!\n<emoji document_id=4906943755644306322>🌐</emoji> <a href='{cleared_url}'>{ytitle}</a>\n<emoji document_id=5278472999572349966>👤</emoji> Author: {author}.",
        "ysuccessm": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Download successful!",
        "yuploading": "<emoji document_id=5276220667182736079>⬇️</emoji> <b>[May take a while]</b> | Uploading result...",
        "yerror": "<emoji document_id=5278578973595427038>🚫</emoji> YTLH Error: <code>{e}</code>.",
        "yno_media": "<emoji document_id=5278578973595427038>🚫</emoji> No media available",
        "yargs": "<emoji document_id=5278578973595427038>🚫</emoji> Provide a YouTube video link!",
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> No streams in allowed resolution! To fix, enter: <code>{pref}fcfg Media-Downloader allow_high_res True</code>.",
        "config_allow_high_res": "Allow downloading >1080p60 of YouTube? | WARNING: If your device does not support more than 1080p, enabling this setting makes no sense.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>BETA version warning!</b>\n\n<blockquote>All commands labeled <b>BETA/ALPHA/TEST</b> are potentially unstable. This means these commands may often cause errors, malfunction, or not work at all, and sometimes even <b>break the entire module</b>. If you want to avoid this, it is advised to stop using these commands and wait until they are stable. Beta versions are released only after testing, so errors causing total module failure are <b>almost always excluded</b>, but there is no guarantee they won’t occur.</blockquote>",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Server closed connection (104). Possible solution: Enable blocking of video up to 1080p60 in module config (<code>allow_high_res</code>), if it does not help: check the speed of the Internet connection.",
        "show_ytdlh_vname": "Show the title of a YouTube video/author when it is loaded?",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg return Error: <code>{retcode}</code>.",
        "rrs": "[Useful] Channel with information about modules from the developer.",
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Version: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> No updates available.\n\n<emoji document_id=6318862057466759063>🎵</emoji> TikTok API status: {tiktok_status}\n<emoji document_id=6319076999105087378>💚</emoji> Spotify API status: {spotify_status}\n<emoji document_id=6321231062642986364>🩵</emoji> Telegram API status: {tg_status}\n<emoji document_id=6321214415349745664>❤️</emoji> Instagram API status: {insta_status}",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Update available {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Changelog of the new version:</b>\n<blockquote>{remote_changelog}</blockquote>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>To update, use the command:</b></i> <code>{pref}dlm {updlink}</code>.\n\n<emoji document_id=6318862057466759063>🎵</emoji> TikTok API status: {tiktok_status}\n<emoji document_id=6319076999105087378>💚</emoji> Spotify API status: {spotify_status}\n<emoji document_id=6321231062642986364>🩵</emoji> Telegram API status: {tg_status}\n<emoji document_id=6321214415349745664>❤️</emoji> Instagram API status: {insta_status}",
        "_cls_doc": "👑 The best module designed to let you download the media you want without watermarks, service subscription, or author attribution in F/-HD.",
        "ph_succesfully": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Photo successfully downloaded!\n<emoji document_id=5375464961822695044>🎬</emoji> Author: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "downloading_ph": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading <b>HD</b> photo...",
         "api_error_500": "<emoji document_id=5278578973595427038>🚫</emoji> API request error: {}. Try again. This should help.",
         "too_bigyt": "<emoji document_id=5276240711795107620>⚠️</emoji> Your video is too large to upload to this chat. Your video is in this ZIP archive, extract it to watch!",
         "spot_playlist": "<emoji document_id=5318760565902947324>✅</emoji> Playlist {safe_name} has been successfully downloaded, unzip the ZIP archive to get the tracks.\n<emoji document_id=5278305362703835500>🔗</emoji> {cleared_url}.",
         "spot_plload": "<emoji document_id=5276220667182736079>⬇️</emoji> Loading your playlist: {safe_name}...",
         "show_ph_info": "Show a info of video (link, author) after downloading photo of TikTok?",
         "succesfully_ph_minimal": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Photo successfully downloaded!",
         "instload": "<emoji document_id=5276220667182736079>⬇️</emoji> Loading story...",
         "noInst_data": "<emoji document_id=5278578973595427038>🚫</emoji> Download error: the loader did not return the required data to download the story. Please try again later.",
         "instsucces": "<emoji document_id=5318760565902947324>✅</emoji> Story(ies) successfully downloaded!\n<emoji document_id=5316578284429937362>👤</emoji> Author: <a href='https://www.instagram.com/{username}'>{fullname}</a>\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>.",
         "instsucces_min": "<emoji document_id=5318760565902947324>✅</emoji> Story(ies) successfully downloaded!",
         "dwn_err": "<emoji document_id=5278578973595427038>🚫</emoji> An unknown error occurred during download: <code>{e}</code>.",
         "show_stfull": "Show author info + link to the story after downloading?",
         "n_inst_args": "<emoji document_id=5278578973595427038>🚫</emoji> Provide a valid link."
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
        "cfg_show_caption_tgs": "Показывать ли описание у загружаемых историй?",
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
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Видео успешно загружено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Видео успешно загружено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Видео успешно загружено!",
        "tiktok_success_minimal_sd": "<emoji document_id=5318760565902947324>✅</emoji> Видео успешно загружено!",
        "cfg_show_tiktok_info": "Показывать автора и ссылку при загрузке видео из TikTok?",
        "cfg_show_spotify_link": "Показывать ли ссылку на трек при загрузке с Spotify?",
        "cfg_force_hd": "Всегда загружать видео в HD из TikTok (если доступно)?",
        "auto_update_ch": "Автообновлять модуль при новых версиях?",
        "cfg_filter_links": "Фильтровать ли ссылки в описаниях к историям при их загрузке?",
        "ffmpeg_missing": "<emoji document_id=5278578973595427038>🚫</emoji> FFmpeg не установлен в системе. Установите <a href='https://t.me/hikka_talks/631886'>по ссылке</a>.",
        "yapi_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка API: <code>{}</code>.",
        "ysuccess": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Загружено успешно!\n<emoji document_id=4906943755644306322>🌐</emoji> <a href='{cleared_url}'>{ytitle}</a>\n<emoji document_id=5278472999572349966>👤</emoji> Автор: {author}.",
        "ysuccessm": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Загружено успешно!",
        "yuploading": "<emoji document_id=5276220667182736079>⬇️</emoji> <b>[Может быть долго]</b> | Загружаю результат...",
        "yerror": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка: <code>{e}</code>.",
        "yno_media": "<emoji document_id=5278578973595427038>🚫</emoji> Нет доступных медиа",
        "yargs": "<emoji document_id=5278578973595427038>🚫</emoji> Укажи ссылку на YouTube видео!",           
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> Нет потоков в разрешенном разрешении! Чтобы исправить, введите: <code>{pref}fcfg Media-Downloader allow_high_res True</code> <b>(Не всегда помогает)</b>.",
        "config_allow_high_res": "Разрешить скачивание >1080p60 с YouTube? | WARNING: Если ваше устройство не поддерживает больше чем 1080р, смысла разрешать эту настройку нет.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>Предупреждение о BETA-версиях!</b>\n\n<blockquote>Все команды, которые имеют инициалы <b>BETA/ALPHA/TEST</b> — потенциально нестабильны. Это значит, что эти команды могут часто вызывать ошибки или неправильно работать, или вовсе не работать, а иногда и вообще <b>сломать работу всего модуля</b>. Если вы не хотите этого, советуется больше не использовать эти команды, и ждать пока они будут стабильно реализованы. Бета версии выходят только после их тестирования, так что ошибки по типу полной поломки модуля <b>почти всегда исключены</b>, но нету гарантии что их не будет.</blockquote>",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Сервер закрыл соединение (104). Возможные решения: Включить блокировку максимального качества загрузки видео в 1080р60 в конфиге модуля (<code>allow_high_res</code>), если не помогает, то проверить скорость интернета. Скорее всего, видео слишком долгое/качественное, от чего занимает слишком много места.",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg вернул ошибку: <code>{retcode}</code>.",
        "show_ytdlh_vname": "Показывать ли название видео/автора при загрузке с YouTube?",
        "rrs": "[Полезно] Канал с информацией о модулях от разработчика.",
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Версия: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> Обновлений нет.\n\n<emoji document_id=6318862057466759063>🎵</emoji> Статус TikTok загрузчика: {tiktok_status}\n<emoji document_id=6319076999105087378>💚</emoji> Статус Spotify загрузчика: {spotify_status}\n<emoji document_id=6321231062642986364>🩵</emoji> Статус Telegram загрузчика: {tg_status}\n<emoji document_id=6321214415349745664>❤️</emoji> Статус Instagram загрузчика: {insta_status}",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Доступно обновление {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Описание новой версии:</b>\n<blockquote>{remote_changelog}</blockquote>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>Для обновления, используйте команду:</b></i> <code>{pref}dlm {updlink}</code>.\n\n<emoji document_id=6318862057466759063>🎵</emoji> Статус TikTok загрузчика: {tiktok_status}\n<emoji document_id=6319076999105087378>💚</emoji> Статус Spotify загрузчика: {spotify_status}\n<emoji document_id=6321231062642986364>🩵</emoji> Статус Telegram загрузчика: {tg_status}\n<emoji document_id=6321214415349745664>❤️</emoji> Статус Instagram загрузчика: {insta_status}",
        "_cls_doc": "👑 Лучший модуль, который поможет загрузить нужное вам медиа без водяного знака/подписки сервиса/автора в F/-HD.",
        "ph_succesfully": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Фото успешно загружены!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>", 
        "downloading_ph": "<emoji document_id=5276220667182736079>⬇️</emoji> Загружаю <b>HD</b> фото...",
        "api_error_500": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при запросе к API. Статус: {}. Попробуйте снова. Это должно помочь.",
        "too_bigyt": "<emoji document_id=5276240711795107620>⚠️</emoji> Ваше видео слишком большое, чтобы загрузить его в этот чат. В этом ZIP-архиве ваше видео, распакуйте, чтобы его посмотреть!",
        "spot_playlist": "<emoji document_id=5318760565902947324>✅</emoji> Плейлист {safe_name} загружен успешно, распакуйте ZIP-архив, чтобы получить треки.\n<emoji document_id=5278305362703835500>🔗</emoji> {cleared_url}.",
        "spot_plload": "<emoji document_id=5276220667182736079>⬇️</emoji> Загружаю твой плейлист: {safe_name}...",
        "show_ph_info": "Показывать ли информацию о видео (автор, ссылка) после загрузки фото из TikTok?",
        "ph_succesfully_minimal": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Фото успешно загружены!",
        "instload": "<emoji document_id=5276220667182736079>⬇️</emoji> Загружаю сторис...",
        "noInst_data": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка загрузки: загрузчик не вернул нужных данных для загрузки сториса. Попробуйте снова позже.",
        "instsucces": "<emoji document_id=5318760565902947324>✅</emoji> Сторис(-ы) успешно загружен(-ы)!\n<emoji document_id=5316578284429937362>👤</emoji> Автор: <a href='https://www.instagram.com/{username}'>{fullname}</a>\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>.",
        "instsucces_min": "<emoji document_id=5318760565902947324>✅</emoji> Сторис(-ы) успешно загружен(-ы)!",
        "dwn_err": "<emoji document_id=5278578973595427038>🚫</emoji> При загрузке произошла неизвестная ошибка: <code>{e}</code>.",
        "show_stfull": "Показывать информацию об авторе + ссылку на сторис после загрузки?",
        "n_inst_args": "<emoji document_id=5278578973595427038>🚫</emoji> Предоставьте валидную ссылку на сторис(-ы)."
    }

    strings_ua = {
        "name": "Media-Downloader",
        "no_args_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Вкажіть ім'я користувача та номер історії.",
        "invalid_format_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Формат: tgsload <ім'я_користувача> <номер_історії>`",
        "invalid_number_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Номер історії повинен бути додатним числом.",
        "api_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при запиті до API: {error}",
        "no_stories_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Історії не знайдено.",
        "invalid_index_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Невірний номер історії. Доступний діапазон: 1 - {max_index}",
        "no_url_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> У вибраної історії відсутній URL.",
        "download_error_tgs": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при завантаженні файлу: {error}",
        "success_tgs": "<emoji document_id=5318760565902947324>✅</emoji> Історія успішно завантажена!\n<emoji document_id=6039451237743595514>📎</emoji> <b>Опис:</b> {caption}",
        "success_no_caption_tgs": "<emoji document_id=5318760565902947324>✅</emoji> Історія успішно завантажена!",
        "downloading_tgs": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую історію...",
        "cfg_show_caption_tgs": "Чи показувати опис до завантажених історій?",
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
        "tiktok_success_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Відео успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "tiktok_success_sd": "<emoji document_id=5318760565902947324>✅</emoji> Відео успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Відео успішно завантажено!",
        "tiktok_success_minimal_sd": "<emoji document_id=5318760565902947324>✅</emoji> Відео успішно завантажено!",
        "cfg_show_tiktok_info": "Показувати автора та посилання після завантаженнія відео із TikTok?",
        "cfg_show_spotify_link": "Показувати посилання на трек після завантаження із Spotify?",
        "cfg_force_hd": "Завжди завантажувати відео в HD з TikTok (якщо доступно)?",
        "auto_update_ch": "Автоматично оновлювати модуль при нових версіях?",
        "cfg_filter_links": "Чи фільтрувати посилання в описах до історій при їх завантаженні?",
        "ffmpeg_missing": "<emoji document_id=5278578973595427038>🚫</emoji> FFmpeg не встановлено в системі. Встановіть <a href='https://t.me/hikka_talks/631886'>за посиланням</a>.",
        "yapi_error": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка API: <code>{}</code>.",
        "ysuccess": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Завантажено успішно!\n<emoji document_id=4906943755644306322>🌐</emoji> <a href='{cleared_url}'>{ytitle}</a>\n<emoji document_id=5278472999572349966>👤</emoji> Автор: {author}.",
        "ysuccessm": "<emoji document_id=5318760565902947324>✅</emoji> <b>[F/-HD]</b> Завантажено успішно!",
        "yuploading": "<emoji document_id=5276220667182736079>⬇️</emoji> <b>[Може бути довго]</b> | Завантажую результат...",
        "yerror": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка: <code>{e}</code>.",
        "yno_media": "<emoji document_id=5278578973595427038>🚫</emoji> Немає доступних медіа",
        "yargs": "<emoji document_id=5278578973595427038>🚫</emoji> Вкажи посилання на YouTube відео!",
        "yno_allowed_res": "<emoji document_id=5278578973595427038>🚫</emoji> Немає потоків у дозволеному розширенні! Щоб виправити, введіть: <code>{pref}fcfg Media-Downloader allow_high_res True</code> <b>(Не завжди допомагає)</b>.",
        "config_allow_high_res": "Дозволити завантаження >1080p60 Для Youtube? | WARNING: Якщо ваш пристрій не підтримує більше ніж 1080p, немає сенсу дозволяти цю настройку.",
        "whybeta": "<emoji document_id=5276240711795107620>⚠️</emoji> <b>Попередження про BETA-версії!</b>\n\n<blockquote>Усі команди, які мають ініціали <b>BETA/ALPHA/TEST</b> — потенційно нестабільні. Це означає, що ці команди можуть часто викликати помилки або працювати неправильно, або взагалі не працювати, а іноді і зовсім <b>зламати роботу всього модуля</b>. Якщо ви цього не хочете, рекомендується більше не використовувати ці команди і чекати, поки вони будуть стабільно реалізовані. Бета-версії виходять тільки після тестування, тому помилки на кшталт повного зламу модуля <b>майже завжди виключені</b>, але гарантій немає.</blockquote>",
        "econnreset": "<emoji document_id=5278578973595427038>🚫</emoji> Сервер закрив з’єднання (104). Можливі рішення: Увімкнути блокування максимального якості завантаження відео в 1080p60 у конфігурації модуля (<code>allow_high_res</code>), якщо не допомагає — перевірити швидкість інтернету. Швидше за все, відео надто довге/якісне, через що займає забагато місця.",
        "ffmpeg_berror": "<emoji document_id=5278578973595427038>🚫</emoji> ffmpeg повернув помилку: <code>{retcode}</code>.",
        "show_ytdlh_vname": "Показувати назву відео/автора при завантаженні з YouTube?",
        "rrs": "[Корисно] Канал з інформацією про модулі від розробника.",
        "nupdm": "<emoji document_id=5818774589714468177>🔱</emoji> Версія: {local_version}.\n<emoji document_id=5278578973595427038>🚫</emoji> Оновлень немає.\n\n<emoji document_id=6318862057466759063>🎵</emoji> Статус TikTok завантажувача: {tiktok_status}\n<emoji document_id=6319076999105087378>💚</emoji> Статус Spotify завантажувача: {spotify_status}\n<emoji document_id=6321231062642986364>🩵</emoji> Статус Telegram завантажувача: {tg_status}\n<emoji document_id=6321214415349745664>❤️</emoji> Статус Instagram завантажувача: {insta_status}",
        "updm": "<emoji document_id=5276240711795107620>❕️</emoji>Доступне оновлення {local_version} > {remote_version}.\n<emoji document_id=5434144690511290129>⚕️</emoji><b>Опис нової версії:</b>\n<blockquote>{remote_changelog}</blockquote>\n\n<emoji document_id=5274099962655816924>❗️</emoji><i><b>Для оновлення використайте команду:</b></i> <code>{pref}dlm {updlink}</code>.\n\n<emoji document_id=6318862057466759063>🎵</emoji> Статус TikTok завантажувача: {tiktok_status}\n<emoji document_id=6319076999105087378>💚</emoji> Статус Spotify завантажувача: {spotify_status}\n<emoji document_id=6321231062642986364>🩵</emoji> Статус Telegram завантажувача: {tg_status}\n<emoji document_id=6321214415349745664>❤️</emoji> Статус Instagram завантажувача: {insta_status}",
        "_cls_doc": "👑 Найкращий модуль, який допоможе завантажити потрібне вам медіа без водяного знака/підписки сервісу/автора в F/-HD.",
        "ph_succesfully": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Фото успішно завантажено!\n<emoji document_id=5375464961822695044>🎬</emoji> Автор: {author}\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>",
        "downloading_ph": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую <b>HD</b> фото...",
        "api_error_500": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка при запиті до API. Статус: {}. Спробуйте ще раз. Це може допомогти.",
        "too_bigyt": "<emoji document_id=5276240711795107620>⚠️</emoji> Ваше відео занадто велике, щоб завантажити його в цей чат. У цьому ZIP-архіві ваше відео, розпакуйте його, щоб переглянути!",
        "spot_playlist": "<emoji document_id=5318760565902947324>✅</emoji> Плейлист {safe_name} успішно завантажено, розпакуйте ZIP-архів, щоб отримати треки.\n<emoji document_id=5278305362703835500>🔗</emoji> {cleared_url}.",
        "spot_plload": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую твій плейлист: {safe_name}...",
        "show_ph_info": "Чи показувати автора/посилання на відео після завантажування фото з TikTok?",
        "ph_succesfully_minimal": "<emoji document_id=5318760565902947324>✅</emoji> <b>[HD]</b> Фото успішно завантажено!",
        "instload": "<emoji document_id=5276220667182736079>⬇️</emoji> Завантажую сторіс...",
        "noInst_data": "<emoji document_id=5278578973595427038>🚫</emoji> Помилка завантаження: завантажувач не повернув потрібних даних для завантаження сторіс. Спробуйте пізніше.",
        "instsucces": "<emoji document_id=5318760565902947324>✅</emoji> Сторіс(-и) успішно завантажені!\n<emoji document_id=5316578284429937362>👤</emoji> Автор: <a href='https://www.instagram.com/{username}'>{fullname}</a>\n<emoji document_id=5278305362703835500>🔗</emoji> <code>{cleared_url}</code>.",
        "instsucces_min": "<emoji document_id=5318760565902947324>✅</emoji> Сторіс(-и) успішно завантажені!",
        "dwn_err": "<emoji document_id=5278578973595427038>🚫</emoji> Під час завантаження сталася невідома помилка: <code>{e}</code>.",
        "show_stfull": "Чи показувати інформацію про автора+посилання на сторіс після його завантаження?",
        "n_inst_args": "Надайте валідне посилання на сторіс(-и)."
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
                    except Exception:
                        token = text

                    if user_id:
                        payload = {
                            "userId": user_id,
                            "token": token,
                            "developerKey": "publictoken"
                        }

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

            try:
                async with session.post(self.API_URL_LOG, json=payload) as r:
                    r.raise_for_status()
                    text = (await r.text()).strip()
                    try:
                        data = json.loads(text)
                        return data
                    except Exception as e:
                        log.error(f"e returns via loguser: {e}")
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
                True,
                doc=lambda: self.strings("show_ytdlh_vname"),
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "ph_success_info",
                True,
                doc=lambda: self.strings("show_ph_info"),
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "instfull",
                True,
                doc=lambda: self.strings("show_stfull"),
                validator=loader.validators.Boolean()
            )
        )

    @loader.command(
        ru_doc="Скачать медиа из TikTok.\nИспользование: .tikload <ссылка>.",
        en_doc="Download TikTok media.\nUsage: .tikload <link>.",
        ua_doc="Завантажити медіа із TikTok.\nВикористання: .tikload <посилання>."
    )
    async def tikloadcmd(self, message: Message):
        """This command downloads TikTok mediafiles via link."""

        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_tiktok_url"])
            return

        url = args.strip()
        original_url = url
        cleared_url = clean_social_link(original_url)

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
                
            if self.config["force_hd"]:
                video_url = f"https://www.tikwm.com/video/media/hdplay/{media_id}.mp4"
            else:
                video_url = data.get("data", {}).get("play", "")
                
            if not video_url:
                await utils.answer(message, self.strings["tiktok_no_video"])
                return
                
            if self.config["force_hd"]:
                await utils.answer(message, self.strings["downloading_hd"])
            else:
                await utils.answer(message, self.strings["downloading_sd"])

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_url) as resp:
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
            
            caption = self.strings["tiktok_success_hd" if self.config["force_hd"] else "tiktok_success_sd"].format(username=username, nickname=nickname, cleared_url=cleared_url, author=author) if self.config["show_tiktok_info"] else self.strings["tiktok_success_minimal_hd" if self.config["force_hd"] else "tiktok_success_minimal_sd"].format(username=username, nickname=nickname, cleared_url=cleared_url, author=author)

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

            author_info = data.get("data", {}).get("author", {})
            username = author_info.get("unique_id", "unknown")
            nickname = author_info.get("nickname", "Unknown")
            author = f"<a href='https://www.tiktok.com/@{username}'>{nickname}</a>"

            caption = self.strings["ph_succesfully"].format(username=username, nickname=nickname, cleared_url=cleared_url, author=author) if self.config["ph_success_info"] else self.strings["ph_succesfully_minimal"].format(username=username, nickname=nickname, cleared_url=cleared_url, author=author)

            photo_groups = []
            group = []
            for idx, img_url in enumerate(images, 1):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url) as resp:
                            if resp.status != 200:
                                continue
                            img_bytes = await resp.read()
                    img_stream = io.BytesIO(img_bytes)
                    img_stream.name = f"{media_id}_{idx}.jpg"
                    group.append(img_stream)
                    if len(group) == 10:
                        photo_groups.append(group)
                        group = []
                except Exception:
                    continue
            if group:
                photo_groups.append(group)

            for i, grp in enumerate(photo_groups, 1):
                send_caption = caption if i == len(photo_groups) else None
                await message.client.send_file(
                    message.chat_id,
                    grp,
                    reply_to=message.id,
                    caption=send_caption,
                    parse_mode="HTML")
                
    @loader.command(
        ru_doc="Скачать трек или плейлист с Spotify.\nИспользование: .spot <ссылка>.",
        en_doc="Download Spotify track or playlist.\nUsage: .spot <link>.",
        ua_doc="Завантажити трек або плейлист із Spotify.\nВикористання: .spot <посилання>."
    )
    async def spotcmd(self, message: Message):
        """Download Spotify track or playlist using SpotifyDownloader."""

        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_url"])
            return

        user_url = args.strip()
        cleared_url = clean_social_link(user_url)

        if "/playlist/" in user_url:
            is_playlist = True
            playlist_id = user_url.split("/playlist/")[1].split("?")[0]
        elif "/track/" in user_url:
            is_playlist = False
        else:
            await utils.answer(message, self.strings["invalid_data"].format("URL", "unknown"))
            return

        downloader = SpotifyDownloader(logging_enabled=False)

        if not is_playlist:
            await utils.answer(message, self.strings["downloading"])
            with tempfile.TemporaryDirectory() as tmpdir:
                local_mp3 = Path(tmpdir) / "track.mp3"
                use_fallback = False
                try:
                    mp3_path = await downloader.download(user_url, outfile=local_mp3)
                    if not mp3_path:
                        raise RuntimeError("Failed direct download")
                except RuntimeError:
                    use_fallback = True

                if use_fallback:
                    api_url = f"https://bj-tricks.serv00.net/Spotify-downloader-api/?url={user_url}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api_url) as resp:
                            data = await resp.json()
                            track_data = data.get("data", {})
                            download_link = track_data.get("downloadLink")
                            img_url = track_data.get("imgUrl")
                            async with session.get(download_link) as resp2:
                                with open(local_mp3, "wb") as f:
                                    async for chunk in resp2.content.iter_chunked(1024 * 1024):
                                        if chunk:
                                            f.write(chunk)
                            if isinstance(img_url, str):
                                img_path = Path(tmpdir) / "cover.jpg"
                                async with session.get(img_url) as resp3:
                                    if resp3.status == 200:
                                        with open(img_path, "wb") as f:
                                            async for chunk in resp3.content.iter_chunked(1024 * 256):
                                                if chunk:
                                                    f.write(chunk)
                                try:
                                    audio = MP3(local_mp3, ID3=ID3)
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
                                except Exception:
                                    pass

                caption = (
                    self.strings["done_caption"].format(cleared_url)
                    if self.config["show_spotify_link"]
                    else self.strings["done_caption_minimal"]
                )
                await message.client.send_file(
                    message.chat_id,
                    local_mp3,
                    caption=caption,
                    reply_to=message.id,
                    parse_mode='HTML',
                    voice_note=False,
                )

        else:
            api_url = f"https://logkiya.netlify.app/.netlify/functions/spot-playlister?id={playlist_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    raw_text = await resp.text()
                    playlist_data = json.loads(raw_text)

                playlist_name = playlist_data.get("meta", {}).get("playlistName", "playlist")
                tracks = playlist_data.get("tracks", [])
                if not tracks:
                    await utils.answer(message, self.strings["api_fail"])
                    return

                safe_name = "".join(c for c in playlist_name if c.isalnum() or c in (" ", "_", "-")).rstrip()
                await utils.answer(message, self.strings["spot_plload"].format(safe_name=safe_name))

                with tempfile.TemporaryDirectory() as tmpdir:
                    zip_path = Path(tmpdir) / f"{safe_name}.zip"
                    not_loaded = []
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                        for i, track in enumerate(tracks, 1):
                            track_url = track.get("trackUrl")
                            track_name = track.get("trackName", f"track_{i}")
                            if not track_url:
                                not_loaded.append(f"{track_name} - missing trackUrl")
                                continue

                            mp3_path = Path(tmpdir) / f"track_{i}.mp3"
                            img_path = Path(tmpdir) / f"cover_{i}.jpg"
                            use_fallback = False

                            try:
                                got_file = await downloader.download(track_url, outfile=mp3_path)
                                if not got_file:
                                    use_fallback = True
                            except Exception:
                                use_fallback = True

                            if use_fallback:
                                track_api = f"https://bj-tricks.serv00.net/Spotify-downloader-api/?url={track_url}"
                                async with session.get(track_api) as resp:
                                    track_info = await resp.json()
                                    tdata = track_info.get("data", {})
                                    download_link = tdata.get("downloadLink")
                                    img_url = tdata.get("imgUrl")
                                    async with session.get(download_link) as resp2:
                                        with open(mp3_path, "wb") as f:
                                            async for chunk in resp2.content.iter_chunked(1024 * 1024):
                                                if chunk:
                                                    f.write(chunk)
                                    if isinstance(img_url, str):
                                        async with session.get(img_url) as resp3:
                                            if resp3.status == 200:
                                                with open(img_path, "wb") as f:
                                                    async for chunk in resp3.content.iter_chunked(1024 * 256):
                                                        if chunk:
                                                            f.write(chunk)
                                        try:
                                            audio = MP3(mp3_path, ID3=ID3)
                                            try:
                                                audio.add_tags()
                                            except Exception:
                                                pass
                                            if img_path.exists():
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
                                            not_loaded.append(f"{track_name} - tagging error {e}")

                            safe_track_name = "".join(c for c in track_name if c.isalnum() or c in (" ", "_", "-"))
                            if not safe_track_name:
                                safe_track_name = f"track_{i}"
                            zipf.write(mp3_path, arcname=f"{safe_track_name}.mp3")

                        if not_loaded:
                            readme_path = Path(tmpdir) / "not_loaded_README.txt"
                            with open(readme_path, "w", encoding="utf-8") as f:
                                f.write("The following tracks were not loaded:\n\n")
                                for line in not_loaded:
                                    f.write(line + "\n")
                            zipf.write(readme_path, arcname="not_loaded_README.txt")

                    caption = self.strings["spot_playlist"].format(safe_name=safe_name, cleared_url=cleared_url)
                    await message.client.send_file(message.chat_id, zip_path, caption=caption, reply_to=message.id)

    @loader.command(
        ru_doc="Скачать telegram историю юзера.\nИспользование: .tgsload <юзернейм> <номер_истории>.",
        en_doc="Download telegram story of user.\nUsage: .tgsload <username> <story_number>.",
        ua_doc="Завантажити telegram історію користувача.\nВикористання: .tgsload <юзернейм> <номер_історії>.")
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
                    ua_doc="Завантажити відео з YouTube.\nВикористання: .ytlh <посилання>")
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
            uploader = meta.get("uploader")
            uploader_id = meta.get("uploader_id")
            author = f"<a href='https://youtube.com/{uploader_id}'>{uploader}</a>"
            yurl = args.strip()
            cleared_url = clean_social_link(yurl)
            thumbnail_url = meta.get("thumbnail")

            if not videos:
                await utils.answer(m, self.strings("yno_media"))
                asyncio.run(ensure_nightly(enable_logs=False))
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
                selected_video = max(high_res or videos, key=lambda x: extract_height(x.get("quality", "")))
            else:
                filtered = [v for v in videos if extract_height(v.get("quality", "")) <= 1080]
                selected_video = max(filtered or videos, key=lambda x: extract_height(x.get("quality", "")))

            video_url = selected_video.get("video_url")
            audio_url = selected_video.get("audio_hdplay")
            if not video_url:
                await utils.answer(m, self.strings("yno_media"))
                return

            timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_read=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:

                video_file = "yt_video.mp4"
                async with session.get(video_url) as resp:
                    resp.raise_for_status()
                    with open(video_file, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 512):
                            f.write(chunk)

                if audio_url:
                    audio_file = "yt_audio.m4a"
                    async with session.get(audio_url) as resp:
                        resp.raise_for_status()
                        with open(audio_file, "wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 256):
                                f.write(chunk)

                thumb_bytes = None
                if thumbnail_url:
                    try:
                        async with session.get(thumbnail_url) as resp:
                            if resp.status == 200:
                                thumb_bytes = await resp.read()
                    except Exception:
                        thumb_bytes = None

            if audio_file:
                output_file = "yt_merged.mp4"
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

            zip_sent = False
            if os.path.getsize(send_file) > 2 * 1024 * 1024 * 1024:
                zip_file = send_file + ".zip"
                with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_STORED) as zf:
                    zf.write(send_file, arcname=os.path.basename(send_file))
                send_file = zip_file
                zip_sent = True

            thumb_stream = io.BytesIO(thumb_bytes) if thumb_bytes else None
            if thumb_stream:
                thumb_stream.name = "thumb.jpg"

            caption = self.strings["too_bigyt"] if zip_sent else (self.strings["ysuccessm"] if not self.config["show_ytname"] else self.strings["ysuccess"]).format(ytitle=ytitle, cleared_url=cleared_url, author=author)

            await message.client.send_file(
                message.peer_id,
                send_file,
                caption=caption,
                reply_to=message.reply_to_msg_id,
                thumb=thumb_stream
            )

            await m.delete()

        except Exception as e:
            log.error("YTLH error: {e}.")
            await utils.answer(m, self.strings["yerror"].format(e=e))

        finally:
            for file in [video_file, audio_file, output_file, 'yt_merged.mp4', 'yt_video.mp4', 'yt_audio.m4a']:
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                    except Exception as e:
                        log.error(e)

#    @loader.command(en_doc="BETA WARNING.", ru_doc="BETA ПРЕДУПРЕЖДЕНИЕ.", ua_doc="BETA ПОПЕРЕДЖЕННЯ.")
#    async def whybetavcmd(self, m: Message):
#        """BETA WARNING MESSAGE"""
#        await utils.answer(m, self.strings("whybeta"))


    @loader.command(
        en_doc="Download Instagram story.\nUsage: .instload <link>",
        ru_doc="Загрузить сторис из Instagram.\nИспользование: .instload <ссылка>",
        ua_doc="Завантажити сторіс з Instagram.\nВикористання: .instload <посилання>",
    )
    async def instloadcmd(self, message: Message):
        """Download Instagram story via link."""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["n_inst_args"])
            return

        url = args.strip()
        cleared_url = clean_social_link(url)

        m = await utils.answer(message, self.strings["instload"])

        try:
            api_url = f"https://bj-instagram-dl.ma-coder-x.workers.dev/?url={url}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"API request failed with {resp.status}")
                    data = await resp.json()

            if not data.get("status"):
                await utils.answer(m, self.strings["noInst_data"])
                return

            media_urls = data["data"]["url"]
            metadata = data["data"]["metadata"]
            caption_text = metadata.get("caption") or ""
            username = metadata.get("username") or ""

            try:
                meta_parser = InstaReelMeta()
                author_meta_json = meta_parser.get_author(url)
                author_meta = json.loads(author_meta_json)
                fullname = author_meta["author"]["full_name"]
            except Exception as e:
                fullname = username
                log.error(f"Could not get full_name, error: {e}")

            if self.config["instfull"]:
                caption = self.strings["instsucces"].format(
                    username=username,
                    fullname=fullname,
                    cleared_url=cleared_url
                )
            else:
                caption = self.strings["instsucces_min"]

            for media_url in media_urls:
                is_video = media_url.lower().endswith((".mp4", ".mov", ".mkv"))
                if is_video:
                    await message.client.send_file(
                        message.chat_id,
                        media_url,
                        caption=caption,
                        force_document=False,
                        reply_to=message.id,
                    )
                else:
                    await message.client.send_file(
                        message.chat_id,
                        media_url,
                        caption=caption,
                        force_document=False,
                        reply_to=message.id,
                    )

            await m.delete()

        except Exception as e:
            log.error(f"INSTLOAD error: {e}")
            await utils.answer(
                m,
                self.strings["dwn_err"].format(e=e)
            )

    @loader.command(en_doc="Check module updates.", ru_doc="Проверить обновления модуля.", ua_doc="Перевірити оновлення модуля.")
    async def updcheckcmd(self, message):
        """This command check module updates."""
        pref = self.get_prefix()
        updlink = "https://api.fixyres.com/module/Walidname113/KModules/heroku/media-downloader.py"
        metadata_url = "https://api.fixyres.com/module/Walidname113/KModules/heroku/media-downloader.py"

        try:
            module = sys.modules[__name__]
            sys_module = inspect.getmodule(module)
            local_version = tuple(map(int, sys_module.__version__))
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
            remote_version_str = (
                first_line.split("=", 1)[1]
                .strip()
                .strip("()")
                .replace(",", "")
                .replace(" ", ".")
            )
            remote_version = tuple(map(int, remote_version_str.split(".")))
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
                    return "<b>🚫 ERROR. More info in logs.</b>"

            async def check_spotify():
                async with aiohttp.ClientSession() as session:
                    ok = False
                    test_url = "https://open.spotify.com/track/2re6FKxMAOBgQMl0V58U0p"
                    downloader = SpotifyDownloader(logging_enabled=False)
                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            test_path = Path(tmpdir) / "check.mp3"
                            got_file = await downloader.download(test_url, outfile=test_path)
                            if got_file and test_path.exists() and test_path.stat().st_size > 1024:
                                ok = True
                            if test_path.exists():
                                test_path.unlink()
                    except Exception:
                        pass

                    if not ok:
                        try:
                            api_url = f"https://bj-tricks.serv00.net/Spotify-downloader-api/?url={test_url}"
                            async with session.get(api_url) as r:
                                if r.status == 200:
                                    data = await r.json()
                                    dl_link = data.get("data", {}).get("downloadLink")
                                    if isinstance(dl_link, str) and dl_link.startswith("http"):
                                        ok = True
                        except Exception:
                            pass

                    return "<emoji document_id=5278411813468269386>✔️</emoji>" if ok else "<emoji document_id=5278578973595427038>🚫</emoji>"

            async def check_telegram_story():
                try:
                    async with session.get("https://telegram-story.apis-bj-devs.workers.dev/?username=Kiyatsuka&action=archive") as r:
                        data = await r.json()
                        if data.get("status") is True and data.get("code") == 200:
                            return "<emoji document_id=5278411813468269386>✔️</emoji>"
                        else:
                            return "<emoji document_id=5278578973595427038>🚫</emoji>"
                except Exception as e:
                    log.error(f"Telegram story status checking error: {e}")
                    return "<b>🚫 ERROR. More info in logs.</b>"

            async def check_instagram():
                try:
                    test_url = "https://www.instagram.com/p/DOs7xtbjSlN/?igsh=cHRhbWlocTRpNXg1"
                    api_url = f"https://bj-instagram-dl.ma-coder-x.workers.dev/?url={test_url}"
                    async with session.get(api_url) as r:
                        if r.status != 200:
                            return "<emoji document_id=5278578973595427038>🚫</emoji>"
                        data = await r.json()
                        if data.get("status") is True and r.status == 200:
                            return "<emoji document_id=5278411813468269386>✔️</emoji>"
                        else:
                            return "<emoji document_id=5278578973595427038>🚫</emoji>"
                except Exception as e:
                    log.error(f"Instagram status checking error: {e}")
                    return "<b>🚫 ERROR. More info in logs.</b>"

            tiktok_status, spotify_status, tg_status, insta_status = await asyncio.gather(
                check_tiktok(), check_spotify(), check_telegram_story(), check_instagram()
            )

        if local_version == remote_version:
            await utils.answer(message, self.strings('nupdm').format(
                local_version=".".join(map(str, local_version)),
                tiktok_status=tiktok_status,
                spotify_status=spotify_status,
                tg_status=tg_status,
                insta_status=insta_status
            ))
        elif remote_version > local_version:
            await utils.answer(message, self.strings['updm'].format(
                local_version=".".join(map(str, local_version)),
                remote_version=".".join(map(str, remote_version)),
                remote_changelog=remote_changelog,
                pref=pref,
                updlink=updlink,
                tiktok_status=tiktok_status,
                spotify_status=spotify_status,
                tg_status=tg_status,
                insta_status=insta_status
            ))
        else:
            await utils.answer(message, self.strings('nupdm').format(
                local_version=".".join(map(str, local_version)),
                tiktok_status=tiktok_status,
                spotify_status=spotify_status,
                tg_status=tg_status,
                insta_status=insta_status
            ))
