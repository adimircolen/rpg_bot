# bot/discord_app/cogs/missions.py
from __future__ import annotations
import re

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from bot.app.use_cases.missions import (
    create_mission,
    attach_mission_card,
    list_missions,
    MissionNotFound,
    ValidationError,
)
from bot.discord_app.presenters.embeds import mission_card_embed
from bot.discord_app.views.mission_card import MissionCardView
from bot.app.use_cases.missions import get_mission_card
from bot.app.use_cases.mission_reports import get_mission_report, MissionNotFound as ReportNotFound
from bot.discord_app.security.policy import require_dm


def _parse_datetime_to_iso(dt_str: str) -> str:
    """
    Aceita:
    - 2026-02-17 20:00
    Retorna ISO: 2026-02-17T20:00:00
    (timezone: naive por enquanto; depois a gente fixa -03:00 se quiser)
    """
    dt_str = dt_str.strip().replace("T", " ")
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    return dt.isoformat()


_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class CreateMissionModal(discord.ui.Modal, title="Criar Missão"):
    titulo = discord.ui.TextInput(
        label="Título da missão",
        placeholder="Ex: A Cripta do Sol Partido",
        min_length=3,
        max_length=80,
        required=True,
    )

    data = discord.ui.TextInput(
        label="Data (DD/MM/AAAA)",
        placeholder="Ex: 17/02/2026",
        min_length=10,
        max_length=10,
        required=True,
    )

    hora = discord.ui.TextInput(
        label="Hora (HH:MM)",
        placeholder="Ex: 20:00",
        min_length=5,
        max_length=5,
        required=True,
    )

    vagas = discord.ui.TextInput(
        label="Vagas (opcional)",
        placeholder="Ex: 5",
        required=False,
        max_length=2,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    def _parse_datetime_to_iso(self, data_str: str, hora_str: str) -> str:
        data_str = data_str.strip()
        hora_str = hora_str.strip()

        if not _DATE_RE.match(data_str):
            raise ValueError("Formato de data inválido.")
        if not _TIME_RE.match(hora_str):
            raise ValueError("Formato de hora inválido.")

        dt = datetime.strptime(f"{data_str} {hora_str}", "%d/%m/%Y %H:%M")
        return dt.isoformat()

    async def on_submit(self, interaction: discord.Interaction) -> None:
        title = str(self.titulo.value).strip()
        scheduled_at_iso = self._parse_datetime_to_iso(str(self.data.value), str(self.hora.value))

        vagas_raw = (str(self.vagas.value).strip() if self.vagas.value else "")
        max_slots = None
        if vagas_raw:
            if not vagas_raw.isdigit():
                await interaction.response.send_message(
                    "❌ Vagas inválido. Use apenas números (ex: 5).",
                    ephemeral=True,
                )
                return
            max_slots = int(vagas_raw)

        mission = create_mission(
            actor_discord_user_id=str(interaction.user.id),
            title=title,
            scheduled_at_iso=scheduled_at_iso,
            max_slots=max_slots,
        )
        
        card = get_mission_card(mission.id)

        msg = await interaction.channel.send(
            embed=mission_card_embed(card, None),
            view=MissionCardView(self.bot, mission.id)
        )

        mission = attach_mission_card(
            mission_id=mission.id,
            channel_id=str(interaction.channel.id),
            message_id=str(msg.id),
        )

        await interaction.response.send_message(
            f"✅ Missão criada: **{mission.title}** (`{mission.code}`)",
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # Log no console
        print(f"[CreateMissionModal] Error: {type(error).__name__}: {error}")

        # Mensagem amigável
        msg = (
            "❌ Não consegui criar a missão.\n"
            "Verifique:\n"
            "📅 Data: DD/MM/AAAA (ex: 17/02/2026)\n"
            "🕒 Hora: HH:MM (ex: 20:00)\n"
            "🎯 Vagas: número opcional (ex: 5)\n"
        )

        if isinstance(error, ValidationError):
            msg = f"❌ {str(error)}"
        elif isinstance(error, ValueError):
            msg = (
                "❌ Data ou hora inválida.\n"
                "Use:\n"
                "📅 17/02/2026\n"
                "🕒 20:00"
            )

        # Se já respondeu, usa followup
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


class MissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="missao_criar", description="Criar uma missão (via modal).")
    @require_dm()
    async def missao_criar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateMissionModal(self.bot))

    @app_commands.command(name="missao_listar", description="Listar missões recentes.")
    @app_commands.describe(limite="Quantidade (1-20)")
    async def missao_listar(self, interaction: discord.Interaction, limite: int = 10):
        try:
            limite = max(1, min(20, limite))
            missions = list_missions(limit=limite)

            if not missions:
                await interaction.response.send_message("Não há missões registradas.", ephemeral=True)
                return

            lines = []
            for m in missions:
                lines.append(f"- `{m.id}` `{m.code}` **{m.title}** ({m.status}) @ {m.scheduled_at}")

            await interaction.response.send_message("\n".join(lines), ephemeral=True)
        except Exception:
            await interaction.response.send_message("Erro ao listar missões.", ephemeral=True)

    @app_commands.command(name="missao_ver", description="Ver detalhes de uma missão por ID.")
    @app_commands.describe(id="ID da missão")
    async def missao_ver(self, interaction: discord.Interaction, id: int):
        try:
            card = get_mission_card(id)
            report = None
            try:
                report = get_mission_report(id)
            except ReportNotFound:
                report = None

            await interaction.response.send_message(embed=mission_card_embed(card, report), ephemeral=True)
        except MissionNotFound as e:
            await interaction.response.send_message(str(e), ephemeral=True)
        except Exception:
            await interaction.response.send_message("Erro ao buscar missão.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MissionsCog(bot))
