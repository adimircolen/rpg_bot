import os
import discord
from discord import app_commands
from discord.ext import commands

from bot.infra.repos.guild_config_repo import GuildConfigRepo
from bot.discord_app.security.policy import require_mod


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sync", description="Força sincronização dos comandos slash.")
    async def sync(self, interaction: discord.Interaction):
        # Permissão: apenas admin do servidor
        if not interaction.user.guild_permissions.administrator: # type: ignore
            await interaction.response.send_message(
                "❌ Você não tem permissão para usar este comando.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild_id = os.getenv("GUILD_ID")

        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                synced = await self.bot.tree.sync(guild=guild)
                await interaction.followup.send(
                    f"✅ Sincronizado no servidor (GUILD_ID={guild_id}). "
                    f"Comandos sincronizados: **{len(synced)}**",
                    ephemeral=True
                )
            else:
                synced = await self.bot.tree.sync()
                await interaction.followup.send(
                    f"✅ Sincronizado globalmente. "
                    f"Comandos sincronizados: **{len(synced)}**\n"
                    f"⚠️ Pode demorar para aparecer no Discord.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erro ao sincronizar: `{type(e).__name__}`",
                ephemeral=True
            )

    @app_commands.command(name="config_canal_espolio", description="Configurar canal para espólio.")
    @app_commands.describe(canal="Canal onde espólios serão publicados")
    @require_mod()
    async def config_canal_espolio(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not interaction.guild:
            await interaction.response.send_message("❌ Este comando só funciona em servidores.", ephemeral=True)
            return

        GuildConfigRepo.set_loot_channel(str(interaction.guild.id), str(canal.id))
        await interaction.response.send_message(
            f"✅ Canal de espólio configurado: {canal.mention}",
            ephemeral=True
        )

    @app_commands.command(name="config_canal_relatorio", description="Configurar canal para relatórios.")
    @app_commands.describe(canal="Canal onde relatórios serão publicados")
    @require_mod()
    async def config_canal_relatorio(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not interaction.guild:
            await interaction.response.send_message("❌ Este comando só funciona em servidores.", ephemeral=True)
            return

        GuildConfigRepo.set_report_channel(str(interaction.guild.id), str(canal.id))
        await interaction.response.send_message(
            f"✅ Canal de relatório configurado: {canal.mention}",
            ephemeral=True
        )

    @app_commands.command(name="config_ver", description="Ver configurações do servidor.")
    @require_mod()
    async def config_ver(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Este comando só funciona em servidores.", ephemeral=True)
            return

        config = GuildConfigRepo.get(str(interaction.guild.id))
        
        loot_ch = "Não configurado"
        report_ch = "Não configurado"

        if config:
            if config["loot_channel_id"]:
                loot_ch = f"<#{config['loot_channel_id']}>"
            if config["report_channel_id"]:
                report_ch = f"<#{config['report_channel_id']}>"

        emb = discord.Embed(
            title="⚙️ Configurações do Servidor",
            color=discord.Color.blue()
        )
        emb.add_field(name="Canal de Espólio", value=loot_ch, inline=False)
        emb.add_field(name="Canal de Relatórios", value=report_ch, inline=False)

        await interaction.response.send_message(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
