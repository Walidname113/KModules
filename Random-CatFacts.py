# -- coding: utf-8 --
# Copyright (c) 2025 Walidname113
# This file is part of Random-CatFacts and is licensed under the GNU AGPLv3.
# See the LICENSE file in the root of the repository for full license text.
# Original repository: https://github.com/Walidname113/KModules
# This code is provided "as is", without warranty of any kind.
# -------------------------------------------------
# scope: hikka_only
#scope: hikka_min 1.6.2
# requires: aiohttp
# meta developer: @RenaYugen

import aiohttp
from .. import loader, utils
from hikkatl.types import Message
import asyncio

mversion = "v1.0.0"

@loader.tds
class CatFacts(loader.Module):
    """The module will cover facts about felines."""

    strings = {
        "name": "Random-CatFacts",
        "catfacts": "<emoji document_id=5345996430995638059>🐱</emoji> <i><b>Fact(s) about felids:</b></i> {facts}",
        "cfg_factscount": "Number of facts per message, max: 20.",
        "cfg_factslang": "Language of facts (rus, eng, ukr).",
        "error_fetch": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Error fetching facts:</b></i> <code>{error}</code>.",
        "error_lang": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Unsupported language code:</b></i> <code>{lang}</code>. | Supported langs:  <code>rus</code>, <code>eng</code>, <code>ukr</code>.",
        "auto_update_ch": "Autoupdate(?) module via new versions."
    }

    strings_ru = {
        "name": "Random-CatFacts",
        "catfacts": "<emoji document_id=5345996430995638059>🐱</emoji> <i><b>Факт(ы) о кошачьих:</b></i> {facts}",
        "cfg_factscount": "Количество фактов в сообщении, максимально: 20.",
        "cfg_factslang": "Язык фактов (rus, eng, ukr).",
        "error_fetch": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Ошибка при получении фактов:</b></i> <code>{error}</code>",
        "error_lang": "<emoji document_id=5278578973595427038>🚫</emoji> <i><b>Неподдерживаемый код языка:</b></i> <code>{lang}</code> | Поддерживаемые: <code>rus</code>, <code>eng</code>, <code>ukr</code>.",
        "auto_update_ch": "Автообновлять ли модуль при новых версиях."
    }

    SUPPORTED_LANGS = {"rus", "eng", "ukr"}

    async def check_for_updates(self):
        import os
        import sys
        from pathlib import Path

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

            module_path = None
            try:
                module_path = Path(__file__).resolve()
            except NameError:
                module_path = getattr(sys.modules.get(__name__), '__file__', None)
                if module_path:
                    module_path = Path(module_path).resolve()
                else:
                    cwd = Path(os.getcwd())
                    candidates = list(cwd.glob('*CatFacts*.py'))
                    if candidates:
                        module_path = candidates[0].resolve()
                    else:
                        module_path = cwd / f"{module_name.replace(' ', '')}.py"

            with open(module_path, "w", encoding="utf-8") as f:
                f.write(new_code)

    def __init__(self):
        super().__init__()
        asyncio.create_task(self.check_for_updates())
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
                validator=loader.validators.Boolean(),            
        )
        
    @loader.command(en_doc="| Some fact of a cats…", ru_doc="| Рандомный факт про котят…")
    async def catfactcmd(self, message: Message):
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
            facts = " | ".join(facts_list)

            await utils.answer(message, self.strings["catfacts"].format(facts=facts))
        except Exception as e:
            await utils.answer(message, self.strings["error_fetch"].format(error=str(e)))
