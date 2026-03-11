from __future__ import annotations

import discord
from discord import app_commands


# ✅ Configure aqui (IDs de roles do seu servidor)
ROLE_IDS = {
    "DM": 0,         # << troque para o Role ID de Mestre
    "MOD": 0,        # << troque para o Role ID de Moderador
}

# Alternativa: usar nomes (menos estável), mas útil no começo
ROLE_NAMES = {
    "DM": {"Mestre", "DM"},
    "MOD": {"Moderador", "Mod"},
}


def _has_any_role_by_id(member: discord.Member, *role_ids: int) -> bool:
    ids = {r.id for r in member.roles}
    return any(rid in ids for rid in role_ids if rid)


def _has_any_role_by_name(member: discord.Member, names: set[str]) -> bool:
    rnames = {r.name for r in member.roles}
    return any(n in rnames for n in names)


def is_guild(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None and isinstance(interaction.user, discord.Member)


def require_guild():
    """Check para garantir que o comando rode só em servidor."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not is_guild(interaction):
            raise app_commands.CheckFailure("Este comando só pode ser usado dentro de um servidor.")
        return True
    return app_commands.check(predicate)


def require_player():
    """
    Player = qualquer membro do servidor (não precisa role).
    Útil para impedir DM e manter padrão.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if not is_guild(interaction):
            raise app_commands.CheckFailure("Este comando só pode ser usado dentro de um servidor.")
        return True
    return app_commands.check(predicate)


def require_dm():
    """Somente Mestres (role) OU Administrador/Manage Guild."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not is_guild(interaction):
            raise app_commands.CheckFailure("Este comando só pode ser usado dentro de um servidor.")

        member: discord.Member = interaction.user

        # Permissões fortes do Discord
        perms = member.guild_permissions
        if perms.administrator or perms.manage_guild:
            return True

        # Role por ID (preferido)
        dm_id = int(ROLE_IDS.get("DM") or 0)
        if dm_id and _has_any_role_by_id(member, dm_id):
            return True

        # Fallback por nome (se id ainda não foi configurado)
        if _has_any_role_by_name(member, ROLE_NAMES["DM"]):
            return True

        raise app_commands.CheckFailure("Você precisa ser **Mestre** para usar este comando.")
    return app_commands.check(predicate)


def require_mod():
    """Somente Moderadores (role) OU Manage Messages/Manage Guild/Administrator."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not is_guild(interaction):
            raise app_commands.CheckFailure("Este comando só pode ser usado dentro de um servidor.")

        member: discord.Member = interaction.user
        perms = member.guild_permissions
        if perms.administrator or perms.manage_guild or perms.manage_messages:
            return True

        mod_id = int(ROLE_IDS.get("MOD") or 0)
        if mod_id and _has_any_role_by_id(member, mod_id):
            return True

        if _has_any_role_by_name(member, ROLE_NAMES["MOD"]):
            return True

        raise app_commands.CheckFailure("Você precisa ser **Moderador** para usar este comando.")
    return app_commands.check(predicate)


# ===== Helpers para Views/Modals (botões) =====

def ensure_member(interaction: discord.Interaction) -> discord.Member:
    if not is_guild(interaction):
        raise PermissionError("Este comando só pode ser usado dentro de um servidor.")
    return interaction.user  # type: ignore


def assert_dm(interaction: discord.Interaction) -> None:
    member = ensure_member(interaction)
    perms = member.guild_permissions
    if perms.administrator or perms.manage_guild:
        return

    dm_id = int(ROLE_IDS.get("DM") or 0)
    if dm_id and _has_any_role_by_id(member, dm_id):
        return

    if _has_any_role_by_name(member, ROLE_NAMES["DM"]):
        return

    raise PermissionError("Você precisa ser Mestre para isso.")


def assert_mod(interaction: discord.Interaction) -> None:
    member = ensure_member(interaction)
    perms = member.guild_permissions
    if perms.administrator or perms.manage_guild or perms.manage_messages:
        return

    mod_id = int(ROLE_IDS.get("MOD") or 0)
    if mod_id and _has_any_role_by_id(member, mod_id):
        return

    if _has_any_role_by_name(member, ROLE_NAMES["MOD"]):
        return

    raise PermissionError("Você precisa ser Moderador para isso.")
