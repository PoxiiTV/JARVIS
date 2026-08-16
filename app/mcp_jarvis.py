"""MCP stdio: Spotify, noticias y memoria de JARVIS. Sin shell."""
import json
import sys

from .brain import _run_tool, append_memory, remove_memory


TOOLS = [
    {
        "name": "buscar_noticias",
        "description": "Busca noticias recientes (Google News RSS) sobre un tema.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tema": {"type": "string"},
                "dias": {"type": "integer", "default": 3},
            },
            "required": ["tema"],
        },
    },
    {
        "name": "recordar",
        "description": (
            "Guarda una nota en memoria persistente. "
            "categoria: recuerdos, preferencias (tono/reglas) o estado."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "enum": ["recuerdos", "preferencias", "estado"],
                },
                "nota": {"type": "string"},
            },
            "required": ["nota"],
        },
    },
    {
        "name": "olvidar",
        "description": "Borra de la memoria las notas que contengan el texto.",
        "inputSchema": {
            "type": "object",
            "properties": {"texto": {"type": "string"}},
            "required": ["texto"],
        },
    },
    {
        "name": "spotify",
        "description": (
            "Controla Spotify del senor: play, pause, skip, search, status, volume, device."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "query": {"type": "string"},
                "device": {"type": "string"},
                "device_id": {"type": "string"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "estado_sistema",
        "description": "Estado del PC y servicios que menciona la pregunta (tiempo, saldo, menú).",
        "inputSchema": {
            "type": "object",
            "properties": {"pregunta": {"type": "string"}},
            "required": ["pregunta"],
        },
    },
    {
        "name": "avisar",
        "description": "Deja un aviso corto en el HUD del senor (una linea).",
        "inputSchema": {
            "type": "object",
            "properties": {"texto": {"type": "string"}},
            "required": ["texto"],
        },
    },
]


def dispatch(name: str, args: dict) -> dict:
    args = args or {}
    if name == "recordar":
        categoria = str(args.get("categoria") or "preferencias").strip()
        nota = str(args.get("nota") or "").strip()
        if not nota:
            return {"ok": False, "error": "falta la nota"}
        try:
            append_memory(categoria, nota)
            return {"ok": True, "guardado_en": categoria, "nota": nota}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
    if name == "olvidar":
        texto = str(args.get("texto") or "").strip()
        if not texto:
            return {"ok": False, "error": "falta el texto"}
        n = remove_memory(texto)
        return {"ok": True, "borradas": n}
    if name == "estado_sistema":
        pregunta = str(args.get("pregunta") or "").strip()
        if not pregunta:
            return {"ok": False, "error": "falta la pregunta"}
        try:
            from . import services
            return {"ok": True, "estado": services.smart_context(pregunta, [])}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    if name in ("buscar_noticias", "spotify"):
        return _run_tool(name, args)
    if name == "avisar":
        from . import services
        return services.escribir_aviso(str(args.get("texto") or ""))
    return {"ok": False, "error": f"Herramienta desconocida: {name}"}


def _write_rpc(msg: dict):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _read_rpc():
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return _read_rpc()
    return json.loads(line)


def _handle(msg: dict):
    mid = msg.get("id")
    method = msg.get("method") or ""
    params = msg.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jarvis", "version": "1.0"},
            },
        }
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        out = dispatch(name, args)
        text = json.dumps(out, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {"content": [{"type": "text", "text": text}]},
        }
    if mid is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "error": {"code": -32601, "message": f"Metodo desconocido: {method}"},
    }


def main():
    while True:
        msg = _read_rpc()
        if msg is None:
            break
        reply = _handle(msg)
        if reply is not None:
            _write_rpc(reply)


if __name__ == "__main__":
    main()
