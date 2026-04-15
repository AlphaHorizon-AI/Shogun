"""Comprehensive migration script — fixes ALL schema/data mismatches.

Handles:
1. Missing columns on agents table (avatar_url, bushido_settings)
2. Security policy permissions with flat string values
3. Persona seed data with invalid enum values
4. Model routing profile rules with wrong structure
"""

import asyncio
import json
from sqlalchemy import text
from shogun.db.engine import engine, async_session_factory


# Mapping of old persona values -> valid enum values
PERSONA_FIXES = {
    # tone: must be analytical, direct, supportive, strategic
    "tone": {
        "Authoritative": "strategic",
        "Subtle": "analytical",
        "Precise": "analytical",
    },
    # planning_depth: must be low, medium, high
    "planning_depth": {
        "deep": "high",
        "shallow": "low",
    },
    # security_bias: must be strict, balanced, open
    "security_bias": {
        "guarded": "strict",
        "permissive": "open",
    },
    # memory_style: must be conservative, focused, expansive
    "memory_style": {
        "semantic": "focused",
        "episodic": "conservative",
    },
}


async def migrate():
    async with async_session_factory() as session:
        # ── 1. Add missing columns to agents table ─────────────
        print("[1/4] Checking agents table columns...")
        try:
            await session.execute(text("SELECT avatar_url FROM agents LIMIT 1"))
            print("  avatar_url: already exists")
        except Exception:
            await session.rollback()
            await session.execute(text(
                "ALTER TABLE agents ADD COLUMN avatar_url VARCHAR(500) DEFAULT '/shogun-avatar.png'"
            ))
            await session.commit()
            print("  avatar_url: ADDED")

        try:
            await session.execute(text("SELECT bushido_settings FROM agents LIMIT 1"))
            print("  bushido_settings: already exists")
        except Exception:
            await session.rollback()
            default_settings = json.dumps({
                "nightly_consolidation": True,
                "weekly_performance_audit": True,
                "skill_health_check": True,
                "persona_drift_check": False,
            })
            await session.execute(text(
                f"ALTER TABLE agents ADD COLUMN bushido_settings JSON DEFAULT '{default_settings}'"
            ))
            await session.commit()
            print("  bushido_settings: ADDED")

        # ── 2. Fix security policy permissions ─────────────────
        print("\n[2/4] Fixing security policy permissions...")
        result = await session.execute(
            text("SELECT id, name, permissions FROM security_policies")
        )
        rows = result.all()
        fixed_policies = 0

        for row in rows:
            policy_id, name, raw_perms = row
            perms = json.loads(raw_perms) if isinstance(raw_perms, str) else raw_perms
            changed = False

            for key in ["filesystem", "network", "shell", "skills", "subagents", "memory"]:
                val = perms.get(key)
                if isinstance(val, str):
                    if key == "filesystem":
                        perms[key] = {"mode": val}
                    elif key == "network":
                        perms[key] = {"mode": val}
                    elif key == "shell":
                        perms[key] = {"enabled": val == "allowed"}
                    elif key == "skills":
                        perms[key] = {"require_approval": val == "approval_required", "allow_auto_install": val != "approval_required"}
                    elif key == "subagents":
                        perms[key] = {"allow_spawn": val != "disabled", "max_active": 10}
                    elif key == "memory":
                        perms[key] = {"allow_write": True, "allow_bulk_delete": False}
                    changed = True

            # Fix old key names
            if "skill_install" in perms:
                val = perms.pop("skill_install")
                perms["skills"] = {"require_approval": val == "approval_required", "allow_auto_install": val != "approval_required"}
                changed = True
            if "subagent_spawn" in perms:
                val = perms.pop("subagent_spawn")
                perms["subagents"] = {"allow_spawn": val != "disabled", "max_active": 5}
                changed = True

            # Ensure all required sub-objects exist
            for key, default in [
                ("filesystem", {"mode": "scoped"}),
                ("network", {"mode": "allowlist"}),
                ("shell", {"enabled": False}),
                ("skills", {"require_approval": True}),
                ("subagents", {"allow_spawn": True, "max_active": 5}),
                ("memory", {"allow_write": True, "allow_bulk_delete": False}),
            ]:
                if key not in perms:
                    perms[key] = default
                    changed = True

            if changed:
                await session.execute(
                    text("UPDATE security_policies SET permissions = :p WHERE id = :id"),
                    {"p": json.dumps(perms), "id": policy_id}
                )
                print(f"  Fixed: {name}")
                fixed_policies += 1

        if fixed_policies:
            await session.commit()
        print(f"  {fixed_policies} policies updated")

        # ── 3. Fix persona enum values ─────────────────────────
        print("\n[3/4] Fixing persona enum values...")
        result = await session.execute(
            text("SELECT id, name, tone, planning_depth, security_bias, memory_style FROM personas")
        )
        rows = result.all()
        fixed_personas = 0

        for row in rows:
            pid, name, tone, planning_depth, security_bias, memory_style = row
            updates = {}

            if tone in PERSONA_FIXES["tone"]:
                updates["tone"] = PERSONA_FIXES["tone"][tone]
            if planning_depth in PERSONA_FIXES["planning_depth"]:
                updates["planning_depth"] = PERSONA_FIXES["planning_depth"][planning_depth]
            if security_bias in PERSONA_FIXES["security_bias"]:
                updates["security_bias"] = PERSONA_FIXES["security_bias"][security_bias]
            if memory_style in PERSONA_FIXES["memory_style"]:
                updates["memory_style"] = PERSONA_FIXES["memory_style"][memory_style]

            if updates:
                set_clause = ", ".join(f"{k} = :{k}" for k in updates)
                updates["id"] = pid
                await session.execute(
                    text(f"UPDATE personas SET {set_clause} WHERE id = :id"),
                    updates
                )
                print(f"  Fixed: {name} ({', '.join(f'{k}: {v}' for k, v in updates.items() if k != 'id')})")
                fixed_personas += 1

        if fixed_personas:
            await session.commit()
        print(f"  {fixed_personas} personas updated")

        # ── 4. Fix model routing profile rules ─────────────────
        print("\n[4/4] Fixing model routing profile rules...")
        result = await session.execute(
            text("SELECT id, name, rules FROM model_routing_profiles")
        )
        rows = result.all()
        fixed_profiles = 0

        for row in rows:
            profile_id, name, raw_rules = row
            rules = json.loads(raw_rules) if isinstance(raw_rules, str) else raw_rules
            changed = False

            new_rules = []
            for rule in rules:
                if "task_type" not in rule or "primary_model_id" not in rule:
                    # Convert old format to new format
                    new_rule = {
                        "task_type": rule.get("match", "*"),
                        "primary_model_id": "00000000-0000-0000-0000-000000000000",
                        "fallback_model_ids": [],
                    }
                    if "provider" in rule:
                        new_rule["latency_bias"] = rule.get("provider")
                    new_rules.append(new_rule)
                    changed = True
                else:
                    new_rules.append(rule)

            if changed:
                await session.execute(
                    text("UPDATE model_routing_profiles SET rules = :r WHERE id = :id"),
                    {"r": json.dumps(new_rules), "id": profile_id}
                )
                print(f"  Fixed: {name}")
                fixed_profiles += 1

        if fixed_profiles:
            await session.commit()
        print(f"  {fixed_profiles} routing profiles updated")

    await engine.dispose()
    print("\n✅ Migration complete — all data is now schema-compatible.")


if __name__ == "__main__":
    asyncio.run(migrate())
