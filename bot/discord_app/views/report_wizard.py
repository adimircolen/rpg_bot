from __future__ import annotations

import discord
from discord.ext import commands

from bot.app.use_cases.mission_reports import (
    issue_mission_report,
    get_mission_report,
    MissionNotFound,
    ValidationError,
    PermissionDenied,
    InvalidStateError,
    ConflictError,
)
from bot.discord_app.presenters.embeds import mission_report_embed
from bot.infra.repos.guild_config_repo import GuildConfigRepo


class MissionReportModal(discord.ui.Modal, title="Emitir Relatorio"):
    resumo = discord.ui.TextInput(
        label="Resumo da missao",
        placeholder="Relato curto do que aconteceu na sessao",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1500,
    )

    resultado = discord.ui.TextInput(
        label="Resultado (opcional)",
        placeholder="Ex: Missao concluida, falha parcial, fuga...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=1200,
    )

    impactos = discord.ui.TextInput(
        label="Impactos no mundo (opcional)",
        placeholder="O que mudou na lore/mundo",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=1200,
    )

    npcs = discord.ui.TextInput(
        label="NPCs relevantes (opcional)",
        placeholder="Ex: Lorde Armand, Sacerdotisa Lyra...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=1200,
    )

    notas = discord.ui.TextInput(
        label="Notas do mestre (opcional)",
        placeholder="Ganchos, lembretes, ajustes...",
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
            issue_mission_report(
                actor_discord_user_id=str(interaction.user.id),
                mission_id=self.mission_id,
                summary=str(self.resumo.value).strip(),
                outcome=str(self.resultado.value).strip() if self.resultado.value else None,
                impacts=str(self.impactos.value).strip() if self.impactos.value else None,
                npcs=str(self.npcs.value).strip() if self.npcs.value else None,
                notes=str(self.notas.value).strip() if self.notas.value else None,
                allow_override=True,
            )

            await interaction.response.send_message("✅ Relatorio emitido!", ephemeral=True)

            # Publicar no canal configurado se existir
            if interaction.guild:
                config = GuildConfigRepo.get(str(interaction.guild.id))
                report = get_mission_report(self.mission_id)
                emb = mission_report_embed(report)
                
                if config and config["report_channel_id"]:
                    ch = self.bot.get_channel(int(config["report_channel_id"]))
                    if ch:
                        await ch.send(embed=emb)
                    else:
                        await interaction.channel.send(embed=emb)
                else:
                    await interaction.channel.send(embed=emb)

            from bot.discord_app.views.mission_card import _refresh_card
            await _refresh_card(self.bot, self.mission_id)

        except (MissionNotFound, ValidationError, PermissionDenied, InvalidStateError, ConflictError) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao emitir relatorio.", ephemeral=True)
