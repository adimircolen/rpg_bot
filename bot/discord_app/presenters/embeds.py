from __future__ import annotations

from datetime import datetime
import discord

STATUS_EMOJI = {
    "SCHEDULED": "📅",
    "CANCELLED": "❌",
    "IN_PROGRESS": "🟡",
    "AWAITING_LOOT": "💰",
    "COMPLETED": "✅",
}


def _format_dt_ptbr(scheduled_at_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(scheduled_at_iso)
        return dt.strftime("%d/%m/%Y às %H:%M") + " (BRT)"
    except Exception:
        return scheduled_at_iso


def _chunk_list(lines: list[str], empty_text: str) -> str:
    if not lines:
        return empty_text
    # evita estourar limite de field
    text = "\n".join(lines)
    if len(text) > 900:
        return "\n".join(lines[:20]) + "\n…"
    return text


def _clip_text(text: str, limit: int = 900) -> str:
    text = (text or "").strip()
    if not text:
        return "—"
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def mission_card_embed(card, report=None) -> discord.Embed:
    emoji = STATUS_EMOJI.get(card.status, "❔")
    emb = discord.Embed(
        title=f"{emoji} {card.title}",
        description=f"**Código:** `{card.code}`\n**ID:** `{card.id}`",
    )

    emb.add_field(name="Data/Hora", value=_format_dt_ptbr(card.scheduled_at), inline=True)
    emb.add_field(name="Status", value=card.status, inline=True)
    emb.add_field(name="Capacidade", value=str(card.max_slots) if card.max_slots else "—", inline=True)

    interested = []
    selected = []
    reserve = []

    for p in card.participants:
        line = f"- {p.character_name} *(por {p.player_display})*"
        if p.role == "SELECTED":
            selected.append(line)
        elif p.role == "RESERVE":
            reserve.append(line)
        else:
            interested.append(line)

    emb.add_field(
        name="Convocados",
        value=_chunk_list(selected, "_Ainda não convocado._"),
        inline=False,
    )
    emb.add_field(
        name="Reservas",
        value=_chunk_list(reserve, "_Sem reservas._"),
        inline=False,
    )
    emb.add_field(
        name="Inscritos",
        value=_chunk_list(interested, "_Ninguém inscrito ainda._"),
        inline=False,
    )

    if report is not None:
        emb.add_field(name="Relatorio", value=_clip_text(report.summary), inline=False)
        if report.outcome:
            emb.add_field(name="Resultado", value=_clip_text(report.outcome), inline=False)
        if report.impacts:
            emb.add_field(name="Impactos", value=_clip_text(report.impacts), inline=False)
        if report.npcs:
            emb.add_field(name="NPCs", value=_clip_text(report.npcs), inline=False)
        if report.notes:
            emb.add_field(name="Notas", value=_clip_text(report.notes), inline=False)
    elif card.status in {"AWAITING_LOOT", "COMPLETED"}:
        emb.add_field(name="Relatorio", value="_Ainda nao emitido._", inline=False)

    emb.set_footer(text="Inscrição é ilimitada • Convocação define convocados e reservas")
    return emb


def loot_embed(loot) -> discord.Embed:
    emb = discord.Embed(
        title=f"💰 Espólio • Missão #{loot.mission_id} (v{loot.version})",
        description="Espólio oficial emitido pelo mestre.",
    )

    base_xp = "—" if loot.base_xp is None else str(loot.base_xp)
    base_gold = "—" if loot.base_gold is None else str(loot.base_gold)

    emb.add_field(name="XP Base", value=base_xp, inline=True)
    emb.add_field(name="Ouro Base", value=base_gold, inline=True)
    emb.add_field(name="Emitido por", value=f"`{loot.issued_by}`", inline=False)

    # Participantes
    if loot.selected_participants:
        plist = "\n".join([f"- {p['character_name']} *(por {p['player_display']})*" for p in loot.selected_participants])
    else:
        plist = "_Nenhum convocado._"
    emb.add_field(name="Convocados (receberam)", value=plist, inline=False)

    # Itens
    if loot.items:
        ilines = []
        for it in loot.items:
            dest = it.get("assigned_to", "GROUP")
            ilines.append(f"- {it.get('name')} x{it.get('qty', 1)} → **{dest}**")
        emb.add_field(name="Itens", value="\n".join(ilines)[:950], inline=False)
    else:
        emb.add_field(name="Itens", value="_Sem itens._", inline=False)

    if loot.report_bonus:
        cname = loot.report_bonus.get("character_name") or "Desconhecido"
        percent = loot.report_bonus.get("percent", 20)
        emb.add_field(name="Bônus de Relatório", value=f"+{percent}% para **{cname}**", inline=False)

    if loot.notes:
        emb.add_field(name="Notas", value=str(loot.notes)[:950], inline=False)

    return emb


def mission_report_embed(report) -> discord.Embed:
    emb = discord.Embed(
        title=f"📝 Relatório • Missão #{report.mission_id}",
        description=report.summary[:1500],
        color=discord.Color.green()
    )

    if report.outcome:
        emb.add_field(name="Resultado", value=_clip_text(report.outcome), inline=False)
    if report.impacts:
        emb.add_field(name="Impactos no Mundo", value=_clip_text(report.impacts), inline=False)
    if report.npcs:
        emb.add_field(name="NPCs Relevantes", value=_clip_text(report.npcs), inline=False)
    if report.notes:
        emb.add_field(name="Notas do Mestre", value=_clip_text(report.notes), inline=False)

    emb.set_footer(text=f"Emitido por {report.issued_by} • v{report.version}")
    return emb
