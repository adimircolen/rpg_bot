# bot/discord_app/views/loot_wizard.py
from __future__ import annotations

import discord
from discord.ext import commands

from bot.app.use_cases.loot import issue_loot, get_loot, ValidationError, PermissionDenied, InvalidStateError, ConflictError, MissionNotFound
from bot.discord_app.presenters.embeds import loot_embed
from bot.discord_app.security.policy import assert_dm
from bot.infra.repos.guild_config_repo import GuildConfigRepo


class LootModal(discord.ui.Modal, title="Emitir Espólio"):
    xp_base = discord.ui.TextInput(
        label="XP base (opcional)",
        placeholder="Ex: 300",
        required=False,
        max_length=6,
    )

    gold_base = discord.ui.TextInput(
        label="Ouro base (opcional)",
        placeholder="Ex: 150",
        required=False,
        max_length=8,
    )

    notes = discord.ui.TextInput(
        label="Notas (opcional)",
        placeholder="Observações gerais do espólio",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=800,
    )

    items = discord.ui.TextInput(
        label="Itens (opcional, 1 por linha)",
        placeholder="Formato: Nome;Qtd;Destino(GROUP ou nome do convocado)\nEx:\nPoção de Cura;3;GROUP\nAdaga +1;1;Eldrar",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=1200,
    )

    def __init__(self, bot: commands.Bot, mission_id: int):
        super().__init__()
        self.bot = bot
        self.mission_id = mission_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            assert_dm(interaction)
            base_xp = None
            base_gold = None

            xp_raw = (str(self.xp_base.value).strip() if self.xp_base.value else "")
            gold_raw = (str(self.gold_base.value).strip() if self.gold_base.value else "")

            if xp_raw:
                if not xp_raw.isdigit():
                    await interaction.response.send_message("❌ XP base deve ser número inteiro.", ephemeral=True)
                    return
                base_xp = int(xp_raw)

            if gold_raw:
                if not gold_raw.isdigit():
                    await interaction.response.send_message("❌ Ouro base deve ser número inteiro.", ephemeral=True)
                    return
                base_gold = int(gold_raw)

            loot = issue_loot(
                actor_discord_user_id=str(interaction.user.id),
                mission_id=self.mission_id,
                base_xp=base_xp,
                base_gold=base_gold,
                notes=str(self.notes.value).strip() if self.notes.value else None,
                items_multiline=str(self.items.value) if self.items.value else None,
                allow_override=True,
            )

            # Publica no canal (opcional). Por enquanto: manda no mesmo canal da missão via followup.
            emb = loot_embed(loot)
            await interaction.response.send_message("✅ Espólio emitido e missão concluída!", ephemeral=True)
            
            # Publicar no canal configurado se existir
            if interaction.guild:
                config = GuildConfigRepo.get(str(interaction.guild.id))
                if config and config["loot_channel_id"]:
                    ch = self.bot.get_channel(int(config["loot_channel_id"]))
                    if ch:
                        await ch.send(embed=emb)
                    else:
                        await interaction.channel.send(embed=emb)
                else:
                    await interaction.channel.send(embed=emb)
            else:
                await interaction.channel.send(embed=emb)

            from bot.discord_app.views.mission_card import _refresh_card
            await _refresh_card(self.bot, self.mission_id)

        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except (ValidationError, PermissionDenied, InvalidStateError, ConflictError, MissionNotFound) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao emitir espólio.", ephemeral=True)
