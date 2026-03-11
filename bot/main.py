# bot/main.py
from __future__ import annotations

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from bot.infra.db.sqlite import init_db


init_db()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


class DragonTavernBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # Habilita leitura de conteúdo de mensagens
        intents.members = True  # Habilita acesso aos membros do servidor
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        # Carrega Cogs
        await self.load_extension("bot.discord_app.cogs.characters")
        await self.load_extension("bot.discord_app.cogs.admin")
        await self.load_extension("bot.discord_app.cogs.missions")
        # await self.load_extension("bot.discord_app.cogs.loot")
        
        # Comando simples de teste (slash)
        self.tree.add_command(ping_command)

        # Sincroniza comandos no Discord
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            # Copia comandos globais para a guild específica
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.info("Synced %d commands to guild %s", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            logging.info("Synced %d commands globally (may take time to appear).", len(synced))

@app_commands.command(name="ping", description="Teste rápido para ver se o bot está online.")
async def ping_command(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Pong! ✅", ephemeral=True)


def main() -> None:
    setup_logging()
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN não encontrado. Defina no arquivo .env")

    bot = DragonTavernBot()
    bot.run(token)


if __name__ == "__main__":
    main()
