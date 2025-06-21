__version__ = (1, 0, 2)
# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of Random-CatFactsH and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# requires: aiohttp
# meta developer: @RenaYugen
# changelog: 1.0.2 change-log: Changelog added, module auto-update function reworked (requires complete re-download of the module to apply) added _cls_doc.

import aiohttp
from .. import loader, utils
from hikkatl.types import Message
import asyncio
import sys
import inspect
from pathlib import Path
import os
import logging

log = logging.getLogger(f"Random-CatFactsH")

@loader.tds
class CatFactsH(loader.Module):
    """The module will cover facts about felines."""

    strings = {
        "name": "Random-CatFactsH",
        "catfacts": "<emoji document_id=5345996430995638059>🐱</emoji> <i><b>Fact(s) about felids:</b></i>\n<blockquote>{facts}</blockquote>",
        "cfg_factscount": "Number of facts per message, max: 20.",
        "cfg_factslang": "Language of facts (rus, eng, ukr).",
        "error_fetch": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Error fetching facts:</b></i> <code>{error}</code>.",
        "error_lang": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Unsupported language code:</b></i> <code>{lang}</code>. | Supported langs:  <code>rus</code>, <code>eng</code>, <code>ukr</code>.",
        "auto_update_ch": "Autoupdate(?) module via new version.",
        "_cls_doc": "🐱 A module that will tell you a random fact about cats."
    }

    strings_ru = {
        "name": "Random-CatFactsH",
        "catfacts": "<emoji document_id=5345996430995638059>🐱</emoji> <i><b>Факт(ы) о кошачьих:</b></i>\n<blockquote>{facts}</blockquote>",
        "cfg_factscount": "Количество фактов в сообщении, максимально: 20.",
        "cfg_factslang": "Язык фактов (rus, eng, ukr).",
        "error_fetch": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Ошибка при получении фактов:</b></i> <code>{error}</code>",
        "error_lang": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Неподдерживаемый код языка:</b></i> <code>{lang}</code> | Поддерживаемые: <code>rus</code>, <code>eng</code>, <code>ukr</code>.",
        "auto_update_ch": "Автообновлять ли модуль при новых версиях.",
        "_cls_doc": "🐱 Модуль, который расскажет вам случайный факт о кошечках."
    }

    SUPPORTED_LANGS = {"rus", "eng", "ukr"}

    @loader.loop(300, autostart=True)
    async def check_for_updates(self):
        if not self.config.get("auto_update", True):
            return

        metadata_url = "https://raw.githubusercontent.com/Walidname113/KModules/heroku/Random-CatFactsH.py"

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

    def __init__(self):
        super().__init__()
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "factscount", 1,
                doc=lambda: self.strings["cfg_factscount"],
                validator=loader.validators.Integer()
            ),
            loader.ConfigValue(
                "factslang", "rus",
                doc=lambda: self.strings["cfg_factslang"],
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "auto_update", True,
                doc=lambda: self.strings("auto_update_ch"),
                validator=loader.validators.Boolean()
            )
        )

    @loader.command(en_doc="| Some fact of a cats…", ru_doc="| Рандомный факт про котят…")
    async def catfactcmd(self, message: Message):
        """Random facts of a cats…"""
        count = self.config["factscount"]
        if count > 20:
            count = 20
        if count < 1:
            count = 1

        lang = self.config["factslang"].lower()
        if lang not in self.SUPPORTED_LANGS:
            await utils.answer(message, self.strings["error_lang"].format(lang=lang))
            return

        url = "https://meowfacts.herokuapp.com/"
        params = {
            "count": count,
            "lang": lang
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            facts_list = [fact if fact.endswith('.') else fact + '.' for fact in data["data"]]
            facts = "\n\n".join(facts_list)

            await utils.answer(message, self.strings["catfacts"].format(facts=facts))
        except Exception as e:
            await utils.answer(message, self.strings["error_fetch"].format(error=str(e)))
