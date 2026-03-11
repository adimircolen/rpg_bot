# bot/app/use_cases/loot.py
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from bot.infra.repos.loot_repo import LootRepo
from bot.infra.repos.missions_repo import MissionsRepo
from bot.infra.repos.participations_repo import ParticipationsRepo
from bot.infra.repos.mission_reports_repo import MissionReportsRepo


MISSION_STATUS_AWAITING_LOOT = "AWAITING_LOOT"
MISSION_STATUS_COMPLETED = "COMPLETED"


class MissionNotFound(Exception):
    pass


class PermissionDenied(Exception):
    pass


class InvalidStateError(Exception):
    pass


class ConflictError(Exception):
    pass


class ValidationError(Exception):
    pass


@dataclass(frozen=True)
class LootSummaryDTO:
    mission_id: int
    version: int
    issued_by: str
    base_xp: int | None
    base_gold: int | None
    notes: str | None
    items: list[dict[str, Any]]
    selected_participants: list[dict[str, Any]]
    report_bonus: dict[str, Any] | None


def _get_mission(mission_id: int):
    row = MissionsRepo.get_by_id(mission_id)
    if not row:
        raise MissionNotFound("Missão não encontrada.")
    return row


def _parse_items_multiline(items_text: str, selected_names: set[str]) -> list[dict[str, Any]]:
    """
    Formato por linha (opcional):
      Nome do Item ; qtd ; destino
    destino: nome do personagem (exato) OU GROUP

    Ex:
      Poção de Cura;3;GROUP
      Adaga +1;1;Eldrar
    """
    items_text = (items_text or "").strip()
    if not items_text:
        return []

    items: list[dict[str, Any]] = []
    for idx, line in enumerate(items_text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 1:
            continue

        name = parts[0]
        if not name:
            raise ValidationError(f"Item linha {idx}: nome vazio.")

        qty = 1
        dest = "GROUP"

        if len(parts) >= 2 and parts[1]:
            if not parts[1].isdigit():
                raise ValidationError(f"Item linha {idx}: quantidade inválida.")
            qty = int(parts[1])
            if qty < 1 or qty > 999:
                raise ValidationError(f"Item linha {idx}: quantidade fora do intervalo.")

        if len(parts) >= 3 and parts[2]:
            dest = parts[2]
            if dest != "GROUP" and dest not in selected_names:
                raise ValidationError(
                    f"Item linha {idx}: destino '{dest}' não é um convocado. Use GROUP ou o nome do personagem convocado."
                )

        items.append({"name": name, "qty": qty, "assigned_to": dest})

    return items


def issue_loot(
    actor_discord_user_id: str,
    mission_id: int,
    base_xp: int | None,
    base_gold: int | None,
    notes: str | None,
    items_multiline: str | None,
    allow_override: bool = False,
) -> LootSummaryDTO:
    mission = _get_mission(mission_id)

    if mission["status"] != MISSION_STATUS_AWAITING_LOOT:
        raise InvalidStateError("Só é possível emitir espólio quando a missão está em AWAITING_LOOT.")

    if str(mission["dm_discord_user_id"]) != str(actor_discord_user_id) and not allow_override:
        raise PermissionDenied("Somente o mestre pode emitir o espólio.")

    if LootRepo.get(mission_id):
        raise ConflictError("Já existe espólio para esta missão.")

    # participantes (selecionados)
    parts = ParticipationsRepo.list_by_mission(mission_id)
    selected = [p for p in parts if p["role"] == "SELECTED"]
    if not selected:
        raise ValidationError("Não há convocados (SELECTED) para receber espólio.")

    selected_names = {p["character_name"] for p in selected}
    items = _parse_items_multiline(items_multiline or "", selected_names)

    report_bonus = None
    report_row = MissionReportsRepo.get(mission_id)
    if report_row:
        report_payload = json.loads(report_row["payload_json"])
        report_bonus = {
            "discord_user_id": str(report_row["issued_by_discord_user_id"]),
            "character_name": report_payload.get("character_name"),
            "percent": 20,
        }

    payload = {
        "base": {"xp": base_xp, "gold": base_gold},
        "notes": notes,
        "items": items,
        "selected_participants": [
            {
                "player_display": p["player_display"],
                "character_id": int(p["character_id"]),
                "character_name": p["character_name"],
            }
            for p in selected
        ],
        "report_bonus": report_bonus,
        "version": 1,
    }

    payload_json = json.dumps(payload, ensure_ascii=False)

    try:
        LootRepo.create(mission_id, actor_discord_user_id, payload_json, version=1)
    except sqlite3.IntegrityError:
        raise ConflictError("Já existe espólio para esta missão.")

    # ✅ Marca que os convocados jogaram (para próxima convocação)
    ParticipationsRepo.mark_played_for_selected(mission_id)

    # ✅ Conclui missão
    MissionsRepo.update_status(mission_id, MISSION_STATUS_COMPLETED)

    return LootSummaryDTO(
        mission_id=mission_id,
        version=1,
        issued_by=str(actor_discord_user_id),
        base_xp=base_xp,
        base_gold=base_gold,
        notes=notes,
        items=items,
        selected_participants=payload["selected_participants"],
        report_bonus=report_bonus,
    )


def get_loot(mission_id: int) -> LootSummaryDTO:
    row = LootRepo.get(mission_id)
    if not row:
        raise MissionNotFound("Espólio não encontrado para esta missão.")

    payload = json.loads(row["payload_json"])

    base = payload.get("base", {})
    return LootSummaryDTO(
        mission_id=mission_id,
        version=int(row["version"]),
        issued_by=str(row["issued_by_discord_user_id"]),
        base_xp=base.get("xp"),
        base_gold=base.get("gold"),
        notes=payload.get("notes"),
        items=payload.get("items", []),
        selected_participants=payload.get("selected_participants", []),
        report_bonus=payload.get("report_bonus"),
    )
