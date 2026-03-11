# bot/discord_app/cogs/characters.py
import discord
from discord import app_commands
from discord.ext import commands

from bot.app.use_cases.characters import (
    create_character,
    list_characters,
    set_character_active,
    CharacterAlreadyExists,
    CharacterNotFound,
    NotCharacterOwner,
)


class CharactersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="personagem_criar", description="Criar um novo personagem.")
    @app_commands.describe(nome="Nome do personagem")
    async def personagem_criar(self, interaction: discord.Interaction, nome: str):
        try:
            result = create_character(
                discord_user_id=str(interaction.user.id),
                display_name=interaction.user.display_name,
                name=nome,
            )
            await interaction.response.send_message(
                f"✅ Personagem **{result['name']}** criado com sucesso!",
                ephemeral=True,
            )

        except CharacterAlreadyExists as e:
            await interaction.response.send_message(str(e), ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
        except Exception:
            await interaction.response.send_message(
                "Erro inesperado ao criar personagem.",
                ephemeral=True,
            )

    @app_commands.command(name="personagem_listar", description="Listar seus personagens.")
    async def personagem_listar(self, interaction: discord.Interaction):
        try:
            chars = list_characters(
                discord_user_id=str(interaction.user.id),
                display_name=interaction.user.display_name,
            )

            if not chars:
                await interaction.response.send_message(
                    "Você ainda não tem personagens. Use **/personagem_criar** para criar um.",
                    ephemeral=True,
                )
                return

            ativos = [c for c in chars if c["is_active"]]
            inativos = [c for c in chars if not c["is_active"]]

            lines = []
            if ativos:
                lines.append("**Ativos:**")
                for c in ativos:
                    lines.append(f"- ✅ {c['name']} (`id={c['character_id']}`)")
            if inativos:
                lines.append("\n**Inativos:**")
                for c in inativos:
                    lines.append(f"- ⛔ {c['name']} (`id={c['character_id']}`)")

            await interaction.response.send_message("\n".join(lines), ephemeral=True)

        except Exception:
            await interaction.response.send_message(
                "Erro inesperado ao listar personagens.",
                ephemeral=True,
            )

    @app_commands.command(
        name="personagem_desativar",
        description="Desativar um personagem (ele não aparecerá em seletores).",
    )
    @app_commands.describe(id="ID do personagem (use /personagem_listar para ver)")
    async def personagem_desativar(self, interaction: discord.Interaction, id: int):
        try:
            result = set_character_active(
                actor_discord_user_id=str(interaction.user.id),
                actor_display_name=interaction.user.display_name,
                character_id=id,
                is_active=False,
            )
            await interaction.response.send_message(
                f"⛔ Personagem **{result['name']}** desativado.",
                ephemeral=True,
            )

        except (CharacterNotFound, NotCharacterOwner) as e:
            await interaction.response.send_message(str(e), ephemeral=True)
        except Exception:
            await interaction.response.send_message(
                "Erro inesperado ao desativar personagem.",
                ephemeral=True,
            )

    @app_commands.command(
        name="personagem_ativar",
        description="Ativar um personagem.",
    )
    @app_commands.describe(id="ID do personagem (use /personagem_listar para ver)")
    async def personagem_ativar(self, interaction: discord.Interaction, id: int):
        try:
            result = set_character_active(
                actor_discord_user_id=str(interaction.user.id),
                actor_display_name=interaction.user.display_name,
                character_id=id,
                is_active=True,
            )
            await interaction.response.send_message(
                f"✅ Personagem **{result['name']}** ativado.",
                ephemeral=True,
            )

        except (CharacterNotFound, NotCharacterOwner) as e:
            await interaction.response.send_message(str(e), ephemeral=True)
        except Exception:
            await interaction.response.send_message(
                "Erro inesperado ao ativar personagem.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(CharactersCog(bot))
