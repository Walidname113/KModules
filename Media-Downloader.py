# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of Media-Downloaer and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# meta developer: @RenaYugen
# meta APIs Providers: https://t.me/BJ_devs, https://t.me/Teleservices_api

from hikkatl.types import Message
from .. import loader, utils
import aiohttp
import os
import tempfile
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from urllib.parse import urlparse

mversion = "v1.0.3"

@loader.tds
class MediaDownloaderMod(loader.Module):
    """👑 Multimedia Loader v1.0.2"""

    strings = {
        "name": "Media-Downloader",
        "no_url": "<emoji document_id=5278578973595427038>🚫</emoji> Provide a Spotify track URL.",
        "fetching": "<emoji document_id=6030657343744644592>🔄</emoji> Fetching data...",
        "api_error": "<emoji document_id=5278578973595427038>🚫</emoji> API request failed. Status: {}",
        "api_exception": "<emoji document_id=5278578973595427038>🚫</emoji> API request error: {}",
        "api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Failed to get track data.",
        "invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Invalid API data. downloadLink: {}, imgUrl: {}",
        "downloading": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading track...",
        "download_error": "<emoji document_id=5278578973595427038>🚫</emoji> Error downloading track. Status: {}",
        "image_error": "<emoji document_id=5278578973595427038>🚫</emoji> Error downloading cover image. Status: {}",
        "file_error": "<emoji document_id=5278578973595427038>🚫</emoji> File download error: {}",
        "tag_error": "<emoji document_id=5278578973595427038>🚫</emoji> Error embedding cover: {}",
        "done_caption": "<emoji document_id=5316653334688446735>✅</emoji> Track successfully downloaded!\n🔗 <code>{}</code>",
        "done_caption_minimal": "<emoji document_id=5316653334688446735>✅</emoji> Track downloaded!",
        "no_tiktok_url": "<emoji document_id=5278578973595427038>🚫</emoji> Provide a TikTok video URL.",
        "tiktok_api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Failed to get video data.",
        "tiktok_invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Invalid TikTok API data.",
        "tiktok_no_video": "<emoji document_id=5278578973595427038>🚫</emoji> No suitable videos found for download.",
        "downloading_hd": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading HD video...",
        "downloading_sd": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading video...",
        "tiktok_success_hd": "<emoji document_id=5316653334688446735>✅</emoji> [HD] Video successfully downloaded!\n🎬 Author: {}\n🔗 <code>{}</code>",
        "tiktok_success_sd": "<emoji document_id=5316653334688446735>✅</emoji> Video downloaded!\n🎬 Author: {}\n🔗 <code>{}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5316653334688446735>✅</emoji> [HD] Video downloaded!",
        "tiktok_success_minimal_sd": "<emoji document_id=5316653334688446735>✅</emoji> Video downloaded!",
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
        "success_tgs": "<emoji document_id=5316653334688446735>✅</emoji> Story downloaded successfully!\nStory caption: {caption}",
        "success_no_caption_tgs": "<emoji document_id=5316653334688446735>✅</emoji> Story downloaded successfully!",
        "downloading_tgs": "<emoji document_id=5276220667182736079>⬇️</emoji> Downloading story...",
        "cfg_show_caption_tgs": "Display captions for downloaded stories.",
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
        "success_tgs": "<emoji document_id=5316653334688446735>✅</emoji> История успешно загружена!\nОписание: {caption}",
        "success_no_caption_tgs": "<emoji document_id=5316653334688446735>✅</emoji> История успешно загружена!",
        "downloading_tgs": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю историю...",
        "cfg_show_caption_tgs": "Показывать описание у загружаемых историй.",
        "no_url": "<emoji document_id=5278578973595427038>🚫</emoji> Укажи ссылку на трек Spotify.",
        "fetching": "<emoji document_id=6030657343744644592>🔄</emoji> Получаю данные...",
        "api_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при запросе к API. Статус: {}",
        "api_exception": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при запросе к API: {}",
        "api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Не удалось получить данные трека.",
        "invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Неверные данные от API. downloadLink: {}, imgUrl: {}",
        "downloading": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю трек...",
        "download_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при скачивании трека. Статус: {}",
        "image_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при скачивании обложки. Статус: {}",
        "file_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при скачивании файлов: {}",
        "tag_error": "<emoji document_id=5278578973595427038>🚫</emoji> Ошибка при добавлении обложки: {}",
        "done_caption": "<emoji document_id=5316653334688446735>✅</emoji> Трек успешно загружен!\n🔗 <code>{}</code>",
        "done_caption_minimal": "<emoji document_id=5316653334688446735>✅</emoji> Трек успешно загружен!",
        "no_tiktok_url": "<emoji document_id=5278578973595427038>🚫</emoji> Укажи ссылку на видео TikTok.",
        "tiktok_api_fail": "<emoji document_id=5278578973595427038>🚫</emoji> Не удалось получить данные видео.",
        "tiktok_invalid_data": "<emoji document_id=5278578973595427038>🚫</emoji> Некорректные данные от TikTok API.",
        "tiktok_no_video": "<emoji document_id=5278578973595427038>🚫</emoji> Не найдено подходящих видео для загрузки.",
        "downloading_hd": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю HD видео...",
        "downloading_sd": "<emoji document_id=5276220667182736079>⬇️</emoji> Скачиваю видео...",
        "tiktok_success_hd": "<emoji document_id=5316653334688446735>✅</emoji> [HD] Видео успешно загружено!\n🎬 Автор: {}\n🔗 <code>{}</code>",
        "tiktok_success_sd": "<emoji document_id=5316653334688446735>✅</emoji> Видео загружено!\n🎬 Автор: {}\n🔗 <code>{}</code>",
        "tiktok_success_minimal_hd": "<emoji document_id=5316653334688446735>✅</emoji> [HD] Видео загружено!",
        "tiktok_success_minimal_sd": "<emoji document_id=5316653334688446735>✅</emoji> Видео загружено!",
        "cfg_show_tiktok_info": "Показывать автора и ссылку в TikTok.",
        "cfg_show_spotify_link": "Показывать ссылку в Spotify.",
        "cfg_force_hd": "Всегда загружать HD (если доступно).",
        "auto_update_ch": "Автообновлять модуль при новых версиях.",
    }

    async def check_for_updates(self):
        if not self.config.get("auto_update", True):
            return

        metadata_url = "https://raw.githubusercontent.com/walidname113/KModules/main/modulesmetadata.txt"
        module_name = self.strings["name"]
        current_version = mversion

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(metadata_url) as resp:
                    if resp.status != 200:
                        return
                    text = await resp.text()
        except Exception:
            return

        latest_version = None
        for line in text.splitlines():
            if line.startswith(f"{module_name}:"):
                latest_version = line.split(":", 1)[1].strip()
                break

        if latest_version and latest_version != current_version:
            raw_module_url = f"https://raw.githubusercontent.com/walidname113/KModules/main/{module_name.replace(' ', '')}.py"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(raw_module_url) as resp:
                        if resp.status != 200:
                            return
                        new_code = await resp.text()
            except Exception:
                return

            module_path = __file__
            with open(module_path, "w", encoding="utf-8") as f:
                f.write(new_code)

            print(f"{module_name} has been updated to version {latest_version}.")
            
    def __init__(self):
        super().__init__()
        asyncio.create_task(self.check_for_updates())
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "show_tiktok_info", True,
                lambda: self.strings("cfg_show_tiktok_info"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_spotify_link", True,
                lambda: self.strings("cfg_show_spotify_link"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "force_hd", True,
                lambda: self.strings("cfg_force_hd"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
            "auto_update", True,
            lambda: self.strings("auto_update_ch"),
            validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_caption",
                True,
                lambda: self.strings("cfg_show_caption_tgs"),
                validator=loader.validators.Boolean(),
            )            
        )

    @loader.command(ru_doc="Скачать видео из TikTok.\nИспользование: .tikload <ссылка>",
                    en_doc="Download TikTok video.\nUsage: .tikload <link>")
    async def tikloadcmd(self, message: Message):
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_tiktok_url"])
            return

        url = args.strip()
        api_url = f"https://tiktok-downloader.apis-bj-devs.workers.dev?url={url}"
        await utils.answer(message, self.strings["fetching"])

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
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_url"])
            return

        user_url = args.strip()
        api_url = f"https://bj-tricks.serv00.net/Spotify-downloader-api/?url={user_url}"
        await utils.answer(message, self.strings["fetching"])

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
        en_doc="Download story of user.\nUsage: .tgsload <username> <story_number>"
    async def tgsloadcmd(self, message):
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
