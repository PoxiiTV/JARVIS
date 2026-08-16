"""Copia plantillas JARVIS a HERMES_HOME y escribe secretos en su .env.

No imprime claves. Uso:
  venv\\Scripts\\python.exe hermes\\aplicar.py
"""
import os
import secrets
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
SRC_SOUL = REPO / "hermes" / "SOUL.md"
SRC_CFG = REPO / "hermes" / "config.yaml"
PY = REPO / "venv" / "Scripts" / "python.exe"


def _leer_env(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _upsert(path: Path, cambios: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    lineas = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pendientes = dict(cambios)
    nuevas = []
    for ln in lineas:
        if "=" in ln and not ln.strip().startswith("#"):
            k = ln.split("=", 1)[0].strip()
            if k in pendientes:
                nuevas.append(f"{k}={pendientes.pop(k)}")
                continue
        nuevas.append(ln)
    if pendientes:
        nuevas.append("")
        nuevas.append("# --- JARVIS / Hermes ---")
        for k, v in pendientes.items():
            nuevas.append(f"{k}={v}")
    path.write_text("\n".join(nuevas) + "\n", encoding="utf-8")


def _parchear_reasoning():
    """Si DeepSeek solo piensa, Hermes usa ese texto como respuesta."""
    path = HERMES_HOME / "hermes-agent" / "agent" / "conversation_loop.py"
    if not path.exists():
        print("AVISO: no esta conversation_loop.py, sin parche reasoning")
        return
    src = path.read_text(encoding="utf-8")
    if "JARVIS_PROMOTE_REASONING" in src:
        print("Parche reasoning: ya aplicado")
        return
    needle = "                    if _has_structured and agent._thinking_prefill_retries < 2:"
    insert = (
        "                    # JARVIS_PROMOTE_REASONING\n"
        "                    if _has_structured:\n"
        "                        _promote = (agent._extract_reasoning(assistant_message) or \"\").strip()\n"
        "                        if _promote:\n"
        "                            _turn_exit_reason = \"reasoning_promoted\"\n"
        "                            logger.info(\n"
        "                                \"Reasoning-only — using as final answer (%d chars)\",\n"
        "                                len(_promote),\n"
        "                            )\n"
        "                            final_response = _promote\n"
        "                            agent._empty_content_retries = 0\n"
        "                            agent._thinking_prefill_retries = 0\n"
        "                            break\n"
    )
    if needle not in src:
        print("AVISO: Hermes cambio conversation_loop, no pude parchear")
        return
    src = src.replace(needle, insert + needle, 1)
    old = (
        '                        final_response = (\n'
        '                            "⚠️ The model produced only internal reasoning and "\n'
        '                            "no final answer, despite retries"\n'
        '                            + (" and fallback" if agent._fallback_chain else "")\n'
        '                            + ". Its last reasoning, which may contain the "\n'
        '                            "answer:\\n\\n" + reasoning_preview\n'
        '                        )'
    )
    new = '                        final_response = reasoning_text.strip()  # JARVIS_PROMOTE_REASONING'
    if old in src:
        src = src.replace(old, new, 1)
    path.write_text(src, encoding="utf-8")
    print("Parche reasoning: aplicado")


def main():
    jarvis = _leer_env(REPO / ".env")
    or_key = jarvis.get("OPENROUTER_API_KEY") or jarvis.get("DEEPSEEK_API_KEY") or ""
    tg = jarvis.get("TELEGRAM_BOT_TOKEN") or ""
    hermes_key = jarvis.get("HERMES_KEY") or secrets.token_urlsafe(24)

    _upsert(REPO / ".env", {
        "HERMES_ENABLED": "1",
        "HERMES_URL": jarvis.get("HERMES_URL") or "http://192.168.1.100:8642/v1",
        "HERMES_KEY": hermes_key,
        "HERMES_MODEL": "hermes-agent",
    })

    HERMES_HOME.mkdir(parents=True, exist_ok=True)
    # No pisar SOUL/config si el senor ya los toco. Solo se crean si faltan.
    dest_soul = HERMES_HOME / "SOUL.md"
    if not dest_soul.exists():
        shutil.copy2(SRC_SOUL, dest_soul)
    dest_cfg = HERMES_HOME / "config.yaml"
    if not dest_cfg.exists():
        cfg = SRC_CFG.read_text(encoding="utf-8")
        cfg = cfg.replace("PYTHON", str(PY).replace("\\", "\\\\"))
        cfg = cfg.replace("REPO", str(REPO).replace("\\", "\\\\"))
        dest_cfg.write_text(cfg, encoding="utf-8")

    env_h = {
        "OPENROUTER_API_KEY": or_key,
        "API_SERVER_ENABLED": "true",
        "API_SERVER_PORT": "8642",
        "API_SERVER_KEY": hermes_key,
        "TELEGRAM_BOT_TOKEN": tg,
        "TELEGRAM_ALLOWED_USERS": jarvis.get("TELEGRAM_ALLOWED_USERS") or "",
        "HERMES_TELEGRAM_DISABLE_FALLBACK_IPS": "true",
    }
    env_h = {k: v for k, v in env_h.items() if v != ""}
    # Si hay LAN, hermes-lan.bat pone 0.0.0.0. No lo pises a localhost.
    if not (jarvis.get("HERMES_LAN_ALLOW") or "").strip():
        env_h["API_SERVER_HOST"] = "127.0.0.1"
    _upsert(HERMES_HOME / ".env", env_h)
    _parchear_reasoning()
    print("OK Hermes home:", HERMES_HOME)
    print("SOUL:", (HERMES_HOME / "SOUL.md").exists())
    print("Telegram token puesto:", bool(tg))
    print("OpenRouter puesto:", bool(or_key))


if __name__ == "__main__":
    main()
