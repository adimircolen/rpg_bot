from __future__ import annotations

import discord
from discord.ext import commands

from bot.app.use_cases.missions import (
    get_mission_card,
    join_mission,
    leave_mission,
    convocate_mission,
    swap_selected_with_reserve,
    start_mission,
    finish_mission,
    MissionNotFound,
    ValidationError,
    PermissionDenied,
    InvalidStateError,
    ConflictError,
)
from bot.app.use_cases.characters import list_characters
from bot.discord_app.presenters.embeds import mission_card_embed
from bot.discord_app.views.loot_wizard import LootModal
from bot.app.use_cases.loot import get_loot
from bot.discord_app.presenters.embeds import loot_embed
from bot.discord_app.security.policy import assert_dm
from bot.discord_app.views.report_wizard import MissionReportModal
from bot.app.use_cases.mission_reports import get_mission_report, MissionNotFound as ReportNotFound



async def _refresh_card(bot: commands.Bot, mission_id: int) -> None:
    card = get_mission_card(mission_id)
    report = None
    try:
        report = get_mission_report(mission_id)
    except ReportNotFound:
        report = None
    if not card.channel_id or not card.card_message_id:
        return

    channel = bot.get_channel(int(card.channel_id)) or await bot.fetch_channel(int(card.channel_id))
    msg = await channel.fetch_message(int(card.card_message_id))
    await msg.edit(embed=mission_card_embed(card, report), view=MissionCardView(bot, mission_id))


class CharacterSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, mission_id: int, choices: list[dict]):
        options = [discord.SelectOption(label=c["name"], value=str(c["character_id"])) for c in choices]
        super().__init__(placeholder="Escolha seu personagem ativo…", min_values=1, max_values=1, options=options)
        self.bot = bot
        self.mission_id = mission_id

    async def callback(self, interaction: discord.Interaction):
        character_id = int(self.values[0])
        try:
            join_mission(
                actor_discord_user_id=str(interaction.user.id),
                actor_display_name=interaction.user.display_name,
                mission_id=self.mission_id,
                character_id=character_id,
            )
            await interaction.response.send_message("✅ Inscrição realizada!", ephemeral=True)
            await _refresh_card(self.bot, self.mission_id)
        except (MissionNotFound, ValidationError, PermissionDenied, InvalidStateError, ConflictError) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao se inscrever.", ephemeral=True)


class CharacterSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, mission_id: int, choices: list[dict]):
        super().__init__(timeout=60)
        self.add_item(CharacterSelect(bot, mission_id, choices))


class ConvocateModal(discord.ui.Modal, title="Convocar participantes"):
    vagas = discord.ui.TextInput(
        label="Vagas (capacidade da mesa)",
        placeholder="Ex: 5",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, bot: commands.Bot, mission_id: int):
        super().__init__()
        self.bot = bot
        self.mission_id = mission_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            assert_dm(interaction)
            raw = str(self.vagas.value).strip()
            if not raw.isdigit():
                await interaction.response.send_message("❌ Vagas deve ser um número.", ephemeral=True)
                return
            seats = int(raw)

            card = convocate_mission(str(interaction.user.id), self.mission_id, seats, allow_override=True)

            selected = [p for p in card.participants if p.role == "SELECTED"]
            reserve = [p for p in card.participants if p.role == "RESERVE"]

            mentions = []
            selected_mentions = " ".join([f"<@{p.player_discord_id}>" for p in selected])
            reserve_mentions = " ".join([f"<@{p.player_discord_id}>" for p in reserve])

            msg_parts = ["📣 **Convocação atualizada!**\n"]
            if selected:
                msg_parts.append(f"**Convocados:** {selected_mentions}")
            if reserve:
                msg_parts.append(f"**Reservas:** {reserve_mentions}")

            await interaction.response.send_message("✅ Convocação processada!", ephemeral=True)
            await interaction.channel.send("\n".join(msg_parts))
            await _refresh_card(self.bot, self.mission_id)

        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except (MissionNotFound, ValidationError, PermissionDenied, InvalidStateError) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao convocar.", ephemeral=True)


class SwapView(discord.ui.View):
    def __init__(self, bot: commands.Bot, mission_id: int, selected_options: list[discord.SelectOption], reserve_options: list[discord.SelectOption]):
        super().__init__(timeout=120)
        self.bot = bot
        self.mission_id = mission_id
        self.selected_id: int | None = None
        self.reserve_id: int | None = None

        self.selected_select = discord.ui.Select(
            placeholder="Escolha um CONVOCADO para virar reserva…",
            min_values=1,
            max_values=1,
            options=selected_options,
        )
        self.reserve_select = discord.ui.Select(
            placeholder="Escolha um RESERVA para virar convocado…",
            min_values=1,
            max_values=1,
            options=reserve_options,
        )

        self.selected_select.callback = self._on_selected  # type: ignore
        self.reserve_select.callback = self._on_reserve    # type: ignore

        self.add_item(self.selected_select)
        self.add_item(self.reserve_select)

    async def _on_selected(self, interaction: discord.Interaction):
        self.selected_id = int(self.selected_select.values[0])
        await interaction.response.send_message("✅ Convocado selecionado. Agora selecione um reserva.", ephemeral=True)

    async def _on_reserve(self, interaction: discord.Interaction):
        self.reserve_id = int(self.reserve_select.values[0])
        await interaction.response.send_message("✅ Reserva selecionado. Use o botão **Confirmar troca**.", ephemeral=True)

    @discord.ui.button(label="Confirmar troca", style=discord.ButtonStyle.primary, emoji="🔁")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_id is None or self.reserve_id is None:
            await interaction.response.send_message("❌ Selecione 1 convocado e 1 reserva antes.", ephemeral=True)
            return
        try:
            assert_dm(interaction)
            swap_selected_with_reserve(
                actor_discord_user_id=str(interaction.user.id),
                mission_id=self.mission_id,
                selected_character_id=self.selected_id,
                reserve_character_id=self.reserve_id,
                allow_override=True,
            )
            await interaction.response.send_message("🔁 Troca realizada!", ephemeral=True)
            await _refresh_card(self.bot, self.mission_id)
        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except (MissionNotFound, ValidationError, PermissionDenied, InvalidStateError) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao trocar.", ephemeral=True)


class MissionCardView(discord.ui.View):
    def __init__(self, bot: commands.Bot, mission_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.mission_id = mission_id

    @discord.ui.button(label="Inscrever", style=discord.ButtonStyle.success, emoji="✅")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            chars = list_characters(str(interaction.user.id), interaction.user.display_name)
            active = [c for c in chars if c["is_active"]]
            if not active:
                await interaction.response.send_message(
                    "Você não tem personagens ativos. Use /personagem_criar ou /personagem_ativar.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                "Escolha seu personagem para se inscrever:",
                view=CharacterSelectView(self.bot, self.mission_id, active),
                ephemeral=True,
            )
        except Exception:
            await interaction.response.send_message("❌ Erro ao abrir seletor.", ephemeral=True)

    @discord.ui.button(label="Remover inscrição", style=discord.ButtonStyle.secondary, emoji="❌")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            leave_mission(
                actor_discord_user_id=str(interaction.user.id),
                actor_display_name=interaction.user.display_name,
                mission_id=self.mission_id,
            )
            await interaction.response.send_message("✅ Inscrição removida.", ephemeral=True)
            await _refresh_card(self.bot, self.mission_id)
        except (MissionNotFound, PermissionDenied, InvalidStateError, ConflictError, ValidationError) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao remover inscrição.", ephemeral=True)

    @discord.ui.button(label="Convocar", style=discord.ButtonStyle.primary, emoji="📣")
    async def convocate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            assert_dm(interaction)
            await interaction.response.send_modal(ConvocateModal(self.bot, self.mission_id))
        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @discord.ui.button(label="Trocar", style=discord.ButtonStyle.primary, emoji="🔁")
    async def swap_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            assert_dm(interaction)
            card = get_mission_card(self.mission_id)

            selected = [p for p in card.participants if p.role == "SELECTED"]
            reserve = [p for p in card.participants if p.role == "RESERVE"]

            if not selected or not reserve:
                await interaction.response.send_message(
                    "Precisa haver pelo menos 1 convocado e 1 reserva para trocar.",
                    ephemeral=True,
                )
                return

            selected_options = [discord.SelectOption(label=p.character_name, value=str(p.character_id)) for p in selected]
            reserve_options = [discord.SelectOption(label=p.character_name, value=str(p.character_id)) for p in reserve]

            await interaction.response.send_message(
                "Selecione quem sai dos convocados e quem entra dos reservas:",
                view=SwapView(self.bot, self.mission_id, selected_options, reserve_options),
                ephemeral=True,
            )
        except Exception:
            await interaction.response.send_message("❌ Erro ao abrir troca.", ephemeral=True)

    @discord.ui.button(label="Travar e iniciar", style=discord.ButtonStyle.success, emoji="🟡")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            assert_dm(interaction)
            start_mission(str(interaction.user.id), self.mission_id, allow_override=True)
            await interaction.response.send_message("🟡 Missão iniciada (lista travada).", ephemeral=True)
            await _refresh_card(self.bot, self.mission_id)
        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except (MissionNotFound, PermissionDenied, InvalidStateError, ValidationError) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao iniciar.", ephemeral=True)

    @discord.ui.button(label="Finalizar", style=discord.ButtonStyle.danger, emoji="🏁")
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            assert_dm(interaction)
            finish_mission(str(interaction.user.id), self.mission_id, allow_override=True)
            await interaction.response.send_message("🏁 Missão finalizada. Próximo passo: emitir espólio.", ephemeral=True)
            await _refresh_card(self.bot, self.mission_id)
        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except (MissionNotFound, PermissionDenied, InvalidStateError) as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Erro inesperado ao finalizar.", ephemeral=True)

    @discord.ui.button(label="Emitir relatorio", style=discord.ButtonStyle.primary, emoji="📝")
    async def report_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MissionReportModal(self.bot, self.mission_id))

    @discord.ui.button(label="Emitir espólio", style=discord.ButtonStyle.success, emoji="💰")
    async def loot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Abre modal (a UC valida status e permissão)
        try:
            assert_dm(interaction)
            await interaction.response.send_modal(LootModal(self.bot, self.mission_id))
        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @discord.ui.button(label="Ver espólio", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def loot_view_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            loot = get_loot(self.mission_id)
            await interaction.response.send_message(embed=loot_embed(loot), ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Ainda não existe espólio para esta missão.", ephemeral=True)

