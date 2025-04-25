# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of URL-Scanner and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# meta developer: @RenaYugen

from .. import loader, utils
import aiohttp
import asyncio
from telethon.tl.types import InputMediaPhotoExternal

mversion = "v1.0.0"

@loader.tds
class UrlScanMod(loader.Module):
    """URL Scanner via urlscan.io."""
    strings = {
        "name": "URL-Scanner",
        "cfg_api_key": "🔑 urlscan.io API key",
        "no_api": "<emoji document_id=5278578973595427038>❌</emoji> API key not set. Use <code>.fcfg URL-Scanner api_key your_key</code>",
        "no_url": "<emoji document_id=5278578973595427038>❌</emoji> Provide a URL: <code>.scan https://example.com</code>",
        "sending": "<emoji document_id=5188180658022808525>⏳</emoji> Submitting URL for scanning...",
        "waiting": "<emoji document_id=5188180658022808525>⏳</emoji> Waiting for results...",
        "error": "<emoji document_id=5463278866724298027>❌</emoji> Error: <code>{err}</code>",
        "caption": (
            "<emoji document_id=5472038559898672363>😎</emoji> <i><b>Result get!</b></i>\n\n"
            "<emoji document_id=5278305362703835500>🔗</emoji> <b>URL:</b> {url}\n"
            "<emoji document_id=5278589204207528856>📨</emoji> <b>Title:</b> {title}\n"
            "<emoji document_id=5276314275994954605>🔨</emoji> <b>Domain:</b> {domain}\n"
            "<emoji document_id=5278647306525108244>🖥</emoji> <b>IP:</b> <code>{ip}</code>\n"
            "<emoji document_id=5276463156741296548>🏳</emoji> <b>Country:</b> {country}\n"
            "<emoji document_id=5276381204470329471>🧠</emoji> <b>Hosting:</b> {asnname}\n"
            "<emoji document_id=5276127848644503161>🤖</emoji> <b>Status Code:</b> {status}\n"
            "<emoji document_id=5276442772826515132>🎨</emoji> <b>MIME:</b> {mime}\n"
            "<emoji document_id=5278753302023004775>ℹ️</emoji> <b>TLS Issuer:</b> {tls_issuer}\n"
            "<emoji document_id=5278753302023004775>ℹ️</emoji> <b>TLS From:</b> <code>{tls_valid_from}</code>\n"
            "<emoji document_id=5278753302023004775>ℹ️</emoji> <b>TLS Days:</b> {tls_valid_days}\n"
            "<emoji document_id=5276463156741296548>🧐</emoji> <b>Suspicious:</b> {malicious}\n"
            "<emoji document_id=5273946310200809961>😉</emoji> <b>Result:</b> <a href=\"{result_url}\">{result_url}</a>"
        ),
        "auto_update_ch": "Auto-update(?) the module when new versions are available.",
    }

    strings_ru = {
        "name": "URL-Scanner",
        "cfg_api_key": "🔑 API-ключ urlscan.io",
        "no_api": "<emoji document_id=5278578973595427038>❌</emoji> API-ключ не указан. Используй <code>.fcfg URL-Scanner api_key твой_ключ</code>.",
        "no_url": "<emoji document_id=5278578973595427038>❌</emoji> Укажи ссылку: <code>.scan https://example.com</code>",
        "sending": "<emoji document_id=5188180658022808525>⏳</emoji> Отправляю ссылку на сканирование...",
        "waiting": "<emoji document_id=5188180658022808525>⏳</emoji> Ожидаю результат...",
        "error": "<emoji document_id=5463278866724298027>❌</emoji> Ошибка: <code>{err}</code>",
        "caption": (
            "<emoji document_id=5472038559898672363>😎</emoji> <i><b>Результат получен!</b></i>\n\n"
            "<emoji document_id=5278305362703835500>🔗</emoji> <b>URL:</b> {url}\n"
            "<emoji document_id=5278589204207528856>📨</emoji> <b>Тайтл:</b> {title}\n"
            "<emoji document_id=5276314275994954605>🔨</emoji> <b>Домен:</b> {domain}\n"
            "<emoji document_id=5278647306525108244>🖥</emoji> <b>IP:</b> <code>{ip}</code>\n"
            "<emoji document_id=5276463156741296548>🏳</emoji> <b>Страна:</b> {country}\n"
            "<emoji document_id=5276381204470329471>🧠</emoji> <b>Хостинг:</b> {asnname}\n"
            "<emoji document_id=5276127848644503161>🤖</emoji> <b>Код ответа:</b> {status}\n"
            "<emoji document_id=5276442772826515132>🎨</emoji> <b>MIME:</b> {mime}\n"
            "<emoji document_id=5278753302023004775>ℹ️</emoji> <b>TLS Issuer:</b> {tls_issuer}\n"
            "<emoji document_id=5278753302023004775>ℹ️</emoji> <b>TLS с:</b> <code>{tls_valid_from}</code>\n"
            "<emoji document_id=5278753302023004775>ℹ️</emoji> <b>TLS дней:</b> {tls_valid_days}\n"
            "<emoji document_id=5276463156741296548>🧐</emoji> <b>Подозрения:</b> {malicious}\n"
            "<emoji document_id=5273946310200809961>😉</emoji> <b>Результат:</b> <a href=\"{result_url}\">{result_url}</a>"
        ),
        "auto_update_ch": "Автообновлять ли модуль при поступлении новых версий.",
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
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                None,
                lambda: self.strings("cfg_api_key")
            ),
            loader.ConfigValue(
                "auto_update", True,
                lambda: self.strings("auto_update_ch"),
                validator=loader.validators.Boolean(),
            )            
        )

    @loader.command(
        ru_doc="Сканирует URL через urlscan.io и выдаёт результаты (скрин, инфа, подозрения и т.д.).",
        en_doc="Scans a URL via urlscan.io and returns details (screenshot, metadata, verdicts, etc)."
    )
    async def scancmd(self, message):
        url = utils.get_args_raw(message)
        if not url:
            await utils.answer(message, self.strings("no_url"))
            return

        api_key = self.config["api_key"]
        if not api_key:
            await utils.answer(message, self.strings("no_api"))
            return

        await utils.answer(message, self.strings("sending"))

        headers = {
            "API-Key": api_key,
            "Content-Type": "application/json"
        }

        visibility_modes = ["public", "unlisted", "private"]
        uuid = None
        last_error = None

        try:
            async with aiohttp.ClientSession() as session:
                for vis in visibility_modes:
                    scan_data = {"url": url, "visibility": vis}
                    async with session.post("https://urlscan.io/api/v1/scan/", json=scan_data, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            uuid = data["uuid"]
                            break
                        elif resp.status == 410:
                            continue
                        else:
                            last_error = f"Status code {resp.status}"
                            break

                if not uuid:
                    raise Exception(last_error or "URL is restricted for all visibility modes")

                await utils.answer(message, self.strings("waiting"))

                for _ in range(10):
                    await asyncio.sleep(1.5)
                    async with session.get(f"https://urlscan.io/api/v1/result/{uuid}/") as result_resp:
                        if result_resp.status == 200:
                            result = await result_resp.json()
                            break
                else:
                    raise Exception("Timeout: result not received")

        except Exception as e:
            await utils.answer(message, self.strings("error").format(err=e))
            return

        info = result.get("page", {})
        verdicts = result.get("verdicts", {}).get("overall", {})
        ips = result.get("lists", {}).get("ips", [])
        if isinstance(ips, list) and ips and isinstance(ips[0], dict):
            ip = ips[0].get("ip", "noData")
        else:
            ip = "Unknown"

        malicious = "Yes" if verdicts.get("malicious", False) else "No"
        caption = self.strings("caption").format(
            url=utils.escape_html(url),
            title=info.get("title", "—"),
            domain=info.get("domain", "—"),
            ip=ip,
            country=info.get("country", "—"),
            asnname=info.get("asnname", "—"),
            status=info.get("status", "—"),
            mime=info.get("mimeType", "—"),
            tls_issuer=info.get("tlsIssuer", "—"),
            tls_valid_from=info.get("tlsValidFrom", "—"),
            tls_valid_days=info.get("tlsValidDays", "—"),
            malicious=malicious,
            result_url=f"https://urlscan.io/result/{uuid}/"
        )

        screenshot_url = f"https://urlscan.io/screenshots/{uuid}.png"

        try:
            await message.client.send_file(
                message.chat_id,
                InputMediaPhotoExternal(screenshot_url),
                caption=caption,
                reply_to=message.id
            )
        except Exception:
            await utils.answer(message, caption)