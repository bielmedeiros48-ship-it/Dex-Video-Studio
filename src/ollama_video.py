from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from media_analysis import transcribe as transcribe_media, write_clip_ass, write_clip_srt, write_cmx3600, write_fcpxml
from media_quality import master_audio as master_audio_file, quality_report, probe
from smart_reframe import write_focus_commands
from video_review import review_video


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("OLLAMA_VIDEO_DATA", str(Path.home() / "IA/Ollama-Video-Studio")))
PROJECTS = DATA_ROOT / "projects"
OLLAMA_URL = "http://127.0.0.1:11434"
VOICE_URL = "http://127.0.0.1:3900"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MODEL = "ollama-video:latest"
WHISPER_MODEL = Path.home() / "IA/modelos/ggml-large-v3-turbo-q5_0.bin"
_agent_reach_candidates = [
    Path(os.environ.get("OLLAMA_VIDEO_AGENT_REACH", "")),
    DATA_ROOT.parent / "repositorios/agent-reach/.venv/Scripts/agent-reach.exe",
    Path.home() / "IA/repositorios/agent-reach/.venv/Scripts/agent-reach.exe",
]
AGENT_REACH = next((path for path in _agent_reach_candidates if str(path) and path.is_file()), _agent_reach_candidates[1])
_audiocpp_candidates = [
    Path(os.environ.get("OLLAMA_VIDEO_AUDIOCPP_CLI", "")),
    DATA_ROOT.parent / "VoiceStudio/engines/audio-cpp/0.9.4/windows-x64/audiocpp_cli.exe",
    Path.home() / "IA/VoiceStudio/engines/audio-cpp/0.9.4/windows-x64/audiocpp_cli.exe",
]
AUDIOCPP_CLI = next((path for path in _audiocpp_candidates if str(path) and path.is_file()), _audiocpp_candidates[1])
DOTS_MODEL = Path.home() / "IA/modelos/VoiceStudio/dots-tts-soar-q8_0.gguf"
AUTO_EDITOR_CANDIDATES = [
    Path.home() / "IA/.venv/Scripts/auto-editor.exe",
    Path(shutil.which("auto-editor") or ""),
]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def request_json(url: str, payload: dict | None = None, timeout: int = 20):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "User-Agent": "OllamaVideoStudio/0.1 (local personal video workflow)",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise
            delay = min(15, int(exc.headers.get("Retry-After") or 5))
            time.sleep(delay)
    raise RuntimeError("A consulta não retornou dados.")


def executable(name: str) -> str | None:
    return shutil.which(name)


def auto_editor() -> Path | None:
    return next((p for p in AUTO_EDITOR_CANDIDATES if str(p) and p.is_file()), None)


def doctor(_args) -> int:
    checks = []
    for label, command in (("FFmpeg", "ffmpeg"), ("FFprobe", "ffprobe")):
        path = executable(command)
        checks.append((label, bool(path), path or "não encontrado"))
    editor = auto_editor()
    checks.append(("Auto-Editor", bool(editor), str(editor or "não encontrado")))
    yt = executable("yt-dlp") or str(DATA_ROOT.parent / "repositorios/voicestudio/.venv/Scripts/yt-dlp.exe")
    checks.append(("yt-dlp", Path(yt).is_file(), yt))
    checks.append(("Agent Reach", AGENT_REACH.is_file(), str(AGENT_REACH)))
    try:
        tags = request_json(f"{OLLAMA_URL}/api/tags")
        names = [m.get("name") for m in tags.get("models", [])]
        checks.append(("Ollama", MODEL in names, ", ".join(names)))
    except Exception as error:
        checks.append(("Ollama", False, str(error)))
    try:
        caps = request_json(f"{VOICE_URL}/v1/audio/capabilities")
        checks.append(("VoiceStudio API", bool(caps.get("local_first")), caps.get("service_version", "sem versão")))
    except Exception as error:
        checks.append(("VoiceStudio API", False, str(error)))
    try:
        engines = request_json(f"{VOICE_URL}/engines/tts", timeout=90)
        active = engines.get("active")
        backend = next((item for item in engines.get("backends", []) if item.get("id") == active), {})
        checks.append(("VoiceStudio motor", bool(backend.get("available")), f"{active}: {backend.get('routing_status', 'desconhecido')}"))
    except Exception as error:
        checks.append(("VoiceStudio motor", False, str(error)))
    for label, ok, detail in checks:
        print(f"[{'OK' if ok else 'PENDENTE'}] {label}: {detail}")
    required = {"FFmpeg", "FFprobe", "Auto-Editor", "Ollama", "VoiceStudio API", "VoiceStudio motor", "Agent Reach"}
    return 0 if all(ok for label, ok, _ in checks if label in required) else 1


def project_path(name: str) -> Path:
    safe = "".join(c for c in name.strip().lower() if c.isalnum() or c in "-_" )
    if not safe or safe != name.strip().lower():
        raise ValueError("Use apenas letras, números, hífen e sublinhado no nome do projeto.")
    return PROJECTS / safe


def isolated_subprocess_environment(home: Path, source: dict[str, str] | None = None) -> dict[str, str]:
    """Keep external helpers functional without forwarding ambient credentials."""
    source = os.environ if source is None else source
    allowed = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP")
    environment = {key: source[key] for key in allowed if source.get(key)}
    environment.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONUTF8": "1"})
    return environment


def new_project(args) -> int:
    target = project_path(args.name)
    if target.exists():
        raise FileExistsError(f"O projeto já existe: {target}")
    for folder in ("01-fontes", "02-roteiro", "03-voz", "04-midia", "05-timeline", "06-revisao", "07-final"):
        (target / folder).mkdir(parents=True, exist_ok=True)
    channel_file = ROOT / "config/channels" / f"{args.channel}.json"
    if not channel_file.is_file():
        raise FileNotFoundError(f"Canal desconhecido: {args.channel}")
    manifest = {
        "schema": "ollama-video-project.v1",
        "name": args.name,
        "channel": args.channel,
        "created_at": now(),
        "state": "created",
        "approval": {"research": False, "script": False, "edit": False, "publish": False},
        "source_policy": "Cada afirmação precisa de URL, data e verificação; cada mídia precisa de direitos registrados."
    }
    (target / "project.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(channel_file, target / "channel.json")
    print(target)
    return 0


def init_weekly_news(args) -> int:
    target = project_path(args.project)
    if not target.is_dir():
        raise FileNotFoundError("Crie o projeto primeiro.")
    try:
        week_start = datetime.strptime(args.week_start, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError("A semana precisa estar em AAAA-MM-DD.") from error
    workflow_source = ROOT / "config/workflows/noticias-semana.json"
    workflow_target = target / "workflow.json"
    shutil.copy2(workflow_source, workflow_target)
    pool_path = target / "01-fontes" / "editorial-pool.json"
    if pool_path.exists():
        raise FileExistsError(f"A semana editorial já existe: {pool_path}")
    pool = {
        "schema": "ollama-video-editorial-pool.v1",
        "week_start": week_start.isoformat(),
        "workflow": "noticias-semana",
        "target_candidates": 45,
        "last_ranked_at": None,
        "candidates": [],
        "daily_runs": [],
        "selected_episodes": [],
    }
    pool_path.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    print(pool_path)
    return 0


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "objective": {"type": "string"},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "research_queries": {"type": "array", "items": {"type": "string"}},
        "production_steps": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"}
    },
    "required": ["objective", "missing_information", "research_queries", "production_steps", "risks", "next_action"]
}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "opening": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "narration": {"type": "string"},
                    "visual_direction": {"type": "string"},
                    "tone": {"type": "string", "enum": ["dense", "neutral", "positive"]},
                    "music_mood": {"type": "string"},
                    "edit_notes": {"type": "array", "items": {"type": "string"}},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["order", "narration", "visual_direction", "tone", "music_mood", "edit_notes", "source_urls"],
            },
        },
        "closing": {"type": "string"},
        "review_flags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "opening", "segments", "closing", "review_flags"],
}

RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "impact": {"type": "number", "minimum": 0, "maximum": 100},
                    "momentum": {"type": "number", "minimum": 0, "maximum": 100},
                    "source_reliability": {"type": "number", "minimum": 0, "maximum": 100},
                    "audience_relevance": {"type": "number", "minimum": 0, "maximum": 100},
                    "story_longevity": {"type": "number", "minimum": 0, "maximum": 100},
                    "visual_availability": {"type": "number", "minimum": 0, "maximum": 100},
                    "rationale": {"type": "string"},
                },
                "required": ["id", "impact", "momentum", "source_reliability", "audience_relevance", "story_longevity", "visual_availability", "rationale"],
            },
        }
    },
    "required": ["items"],
}


def plan(args) -> int:
    target = project_path(args.project)
    manifest = json.loads((target / "project.json").read_text(encoding="utf-8"))
    channel = json.loads((target / "channel.json").read_text(encoding="utf-8"))
    prompt = (
        "Crie somente um plano de produção. Não invente resultados de pesquisa nem diga que executou ferramentas.\n"
        f"Data local: {now()}\nBrief: {args.brief}\n"
        f"Projeto: {json.dumps(manifest, ensure_ascii=False)}\n"
        f"Canal: {json.dumps(channel, ensure_ascii=False)}"
    )
    response = request_json(f"{OLLAMA_URL}/api/generate", {
        "model": MODEL, "prompt": prompt, "stream": False, "format": PLAN_SCHEMA,
        "options": {"temperature": 0.2}
    }, timeout=180)
    result = json.loads(response["response"])
    out = target / "02-roteiro" / "plano-producao.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


def _web_search(query: str, limit: int) -> dict:
    if not AGENT_REACH.is_file():
        raise FileNotFoundError("Agent Reach não está instalado.")
    command = [str(AGENT_REACH), "web", "search", query, "--limit", str(limit)]
    reach_home = Path(os.environ.get(
        "OLLAMA_VIDEO_STATE",
        str(Path.home() / "IA/ollama-video-state"),
    )) / "agent-reach-home"
    reach_home.mkdir(parents=True, exist_ok=True)
    environment = isolated_subprocess_environment(reach_home)
    completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120, env=environment)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("A pesquisa não retornou JSON verificável.") from error


def research(args) -> int:
    target = project_path(args.project) / "01-fontes"
    if not target.is_dir():
        raise FileNotFoundError("Crie o projeto primeiro.")
    result = _web_search(args.query, args.limit)
    record = {"created_at": now(), "query": args.query, "collector": "agent-reach/web", "result": result,
              "warning": "Resultado de busca não é fato confirmado; valide datas e fontes primárias."}
    out = target / f"pesquisa-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


def collect_news(args) -> int:
    target = project_path(args.project) / "01-fontes"
    pool_path = target / "editorial-pool.json"
    if not pool_path.is_file():
        raise FileNotFoundError("Inicialize a semana com init-weekly-news.")
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    result = _web_search(args.query, args.limit)
    items = result.get("items", [])
    existing_urls = {item.get("primary_url") for item in pool.get("candidates", [])}
    added = 0
    stamp = now()
    for item in items:
        url = str(item.get("url") or "").strip()
        if not url or url in existing_urls:
            continue
        pool["candidates"].append({
            "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:12],
            "title": str(item.get("title") or "").strip(),
            "primary_url": url,
            "author": item.get("author"),
            "published_at": item.get("published_at"),
            "snippet": str(item.get("text") or "")[:1200],
            "discovered_at": stamp,
            "query": args.query,
            "verification_status": "unverified",
            "independent_sources": 1,
            "score": None,
            "status": "candidate",
        })
        existing_urls.add(url)
        added += 1
    pool.setdefault("daily_runs", []).append({
        "at": stamp, "query": args.query, "returned": len(items),
        "added": added, "pool_total": len(pool["candidates"]),
    })
    pool_path.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pool": str(pool_path), "returned": len(items), "added": added,
                      "total": len(pool["candidates"]), "target": pool.get("target_candidates", 45)}, ensure_ascii=False))
    return 0


def rank_news(args) -> int:
    target = project_path(args.project) / "01-fontes"
    pool_path = target / "editorial-pool.json"
    if not pool_path.is_file():
        raise FileNotFoundError("Inicialize a semana com init-weekly-news.")
    pool = _load_json(pool_path)
    workflow = _load_json(ROOT / "config/workflows/noticias-semana.json")
    weights = workflow["editorial"]["scoring"]
    candidates = pool.get("candidates", [])
    if not candidates:
        raise RuntimeError("O conjunto editorial ainda não tem candidatas.")
    digest_markers = (
        "resumo", "principais notícias", "notícias principais", "noticiário",
        "jornal da noite", "poder expresso", "notícias do dia", "hoje no ",
        "morning briefing", "daily", "as notícias que", "giro de notícias",
    )
    eligible = []
    for candidate in candidates:
        title = str(candidate.get("title") or "").lower()
        if any(marker in title for marker in digest_markers):
            candidate["ranking_status"] = "discovery_only"
            candidate["score"] = None
        else:
            eligible.append(candidate)
    ratings = {}
    warnings = []
    for offset in range(0, len(eligible), 10):
        batch = eligible[offset:offset + 10]
        compact = [{
            "id": item["id"], "title": item.get("title"), "source": item.get("primary_url"),
            "published_at": item.get("published_at"), "snippet": str(item.get("snippet") or "")[:500],
            "verification_status": item.get("verification_status"), "independent_sources": item.get("independent_sources", 1),
        } for item in batch]
        prompt = (
            "Faça uma classificação editorial PRELIMINAR das pautas abaixo. Não invente métricas, comentários, "
            "visualizações ou confirmação. Uma pauta não verificada deve receber penalidade em source_reliability. "
            "Avalie 0 a 100: impacto, momentum aparente no material fornecido, confiabilidade da fonte, relevância "
            "para público brasileiro, longevidade e disponibilidade visual. Preserve exatamente o id.\n"
            f"Pautas: {json.dumps(compact, ensure_ascii=False)}"
        )
        response = request_json(f"{OLLAMA_URL}/api/generate", {
            "model": MODEL, "prompt": prompt, "stream": False, "format": RANKING_SCHEMA, "think": False,
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 1600},
        }, timeout=300)
        try:
            result = json.loads(response["response"])
        except json.JSONDecodeError:
            warnings.append(f"Lote {offset // 10 + 1} retornou JSON incompleto.")
            continue
        known = {item["id"] for item in batch}
        for item in result.get("items", []):
            if item.get("id") in known:
                ratings[item["id"]] = item
    if not ratings:
        raise RuntimeError("O Ollama não devolveu avaliações estruturadas válidas.")
    for candidate in candidates:
        rating = ratings.get(candidate["id"])
        if not rating:
            continue
        breakdown = {key: min(100, max(0, float(rating[key]))) for key in weights}
        if candidate.get("verification_status") != "verified" or int(candidate.get("independent_sources", 1)) < 2:
            breakdown["source_reliability"] = min(45, breakdown["source_reliability"])
        candidate["score_breakdown"] = breakdown
        candidate["score"] = round(sum(breakdown[key] * float(weights[key]) for key in weights), 2)
        candidate["ranking_rationale"] = rating["rationale"]
        candidate["ranking_status"] = "preliminary_unverified"
    ranked_all = sorted(
        (item for item in candidates if item.get("score") is not None),
        key=lambda item: item["score"],
        reverse=True,
    )
    stopwords = {
        "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em",
        "na", "nas", "no", "nos", "o", "os", "para", "por", "que", "um", "uma",
        "hoje", "nesta", "neste", "novembro", "2026",
    }

    def topic_terms(title: str) -> set[str]:
        plain = unicodedata.normalize("NFKD", title.casefold()).encode("ascii", "ignore").decode("ascii")
        return {word for word in re.findall(r"[a-z0-9]+", plain) if len(word) > 2 and word not in stopwords}

    ranked = []
    for candidate in ranked_all:
        terms = topic_terms(str(candidate.get("title") or ""))
        duplicate = False
        for selected in ranked:
            other = topic_terms(str(selected.get("title") or ""))
            overlap = terms & other
            smaller = min(len(terms), len(other))
            if smaller and len(overlap) >= 2 and len(overlap) / smaller >= 0.25:
                duplicate = True
                candidate["ranking_status"] = "duplicate_topic"
                break
        if not duplicate:
            ranked.append(candidate)
    pool["last_ranked_at"] = now()
    pool["preliminary_top"] = [item["id"] for item in ranked[:args.count]]
    pool["ranking_warnings"] = warnings
    pool_path.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    output = target / "ranking-preliminar.json"
    output.write_text(json.dumps({"created_at": now(), "status": "requires_source_verification", "items": ranked[:args.count], "warnings": warnings}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


def draft(args) -> int:
    target = project_path(args.project)
    ranking_path = target / "01-fontes" / "ranking-preliminar.json"
    if ranking_path.is_file():
        ranked = _load_json(ranking_path).get("items", [])[:5]
        sources = [
            {
                "title": item.get("title"),
                "url": item.get("primary_url"),
                "author": item.get("author"),
                "published_at": item.get("published_at"),
                "text": (item.get("snippet") or "")[:1800],
                "verification_status": item.get("verification_status", "unverified"),
                "independent_sources": item.get("independent_sources", 1),
            }
            for item in ranked
        ]
    else:
        source_files = sorted(
            (target / "01-fontes").glob("pesquisa-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not source_files:
            raise FileNotFoundError("Faça a pesquisa antes de criar o roteiro.")
        research_record = json.loads(source_files[0].read_text(encoding="utf-8"))
        items = research_record.get("result", {}).get("items", [])[: args.max_sources]
        sources = [
            {"title": item.get("title"), "url": item.get("url"), "author": item.get("author"),
             "published_at": item.get("published_at"), "text": (item.get("text") or "")[:1800]}
            for item in items
        ]
    prompt = (
        "Escreva um RASCUNHO de roteiro jornalístico humano e sóbrio usando apenas as fontes abaixo. "
        "Não transforme hipótese em fato. Cada segmento deve listar as URLs que sustentam a narração. "
        "Se duas fontes independentes não confirmarem uma afirmação, inclua isso em review_flags. "
        "Não invente imagens, entrevistas, datas ou citações. Produza EXATAMENTE cinco segmentos, um por pauta, "
        "sem repetir o mesmo acontecimento. O vídeo final deve durar aproximadamente 6 a 10 minutos: abertura "
        "com 50 a 80 palavras, cada segmento com 120 a 180 palavras e encerramento com 50 a 80 palavras. Para cada segmento, "
        "classifique o tom como dense, neutral ou positive; indique uma trilha instrumental discreta e notas de "
        "edição concretas para zoom, destaque de texto, mapas, gráficos, transições naturais e SFX sem exagero.\n"
        f"Objetivo: {args.brief}\nFontes: {json.dumps(sources, ensure_ascii=False)}"
    )
    response = request_json(f"{OLLAMA_URL}/api/generate", {
        "model": MODEL, "prompt": prompt, "stream": False, "format": SCRIPT_SCHEMA, "think": False,
        "options": {"temperature": 0.3, "num_ctx": 8192, "num_predict": 3000},
    }, timeout=240)
    raw_script = str(response.get("response") or "").strip()
    if not raw_script:
        raise RuntimeError("O Ollama terminou sem devolver o roteiro; tente novamente com o conjunto salvo.")
    script = json.loads(raw_script)
    known_urls = {item["url"] for item in sources if item.get("url")}
    cited_urls = {url for segment in script.get("segments", []) for url in segment.get("source_urls", [])}
    unknown = sorted(cited_urls - known_urls)
    if unknown:
        raise RuntimeError(f"O modelo citou fontes não fornecidas: {unknown}")
    out = target / "02-roteiro" / "rascunho-com-fontes.json"
    out.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


def storyboard(args) -> int:
    target = project_path(args.project)
    script_path = target / "02-roteiro" / "rascunho-com-fontes.json"
    if not script_path.is_file():
        raise FileNotFoundError("Crie e revise o rascunho antes do storyboard.")
    script = _load_json(script_path)
    scenes = []
    opening = str(script.get("opening") or "").strip()
    if opening:
        scenes.append({"order": 1, "kind": "opening", "narration": opening,
                       "visual_direction": "Cartela de abertura e imagem principal verificável.",
                       "source_urls": [], "media": [], "transition": "cut", "sound_effect": None,
                       "rights_status": "pending", "approval": "pending"})
    for segment in script.get("segments", []):
        scenes.append({"order": len(scenes) + 1, "kind": "story",
                       "narration": str(segment.get("narration") or "").strip(),
                       "visual_direction": str(segment.get("visual_direction") or "").strip(),
                       "tone": segment.get("tone", "neutral"),
                       "music_mood": str(segment.get("music_mood") or "").strip(),
                       "edit_notes": segment.get("edit_notes", []),
                       "source_urls": segment.get("source_urls", []), "media": [],
                       "transition": "crossfade-natural", "sound_effect": None, "rights_status": "pending",
                       "approval": "pending"})
    closing = str(script.get("closing") or "").strip()
    if closing:
        scenes.append({"order": len(scenes) + 1, "kind": "closing", "narration": closing,
                       "visual_direction": "Síntese visual e encerramento do canal.",
                       "source_urls": [], "media": [], "transition": "cut", "sound_effect": None,
                       "rights_status": "pending", "approval": "pending"})
    if not scenes:
        raise RuntimeError("O roteiro não contém cenas aproveitáveis.")
    result = {"schema": "ollama-video-storyboard.v1", "created_at": now(),
              "source_script": str(script_path), "status": "needs_human_review",
              "rules": {"originals_preserved": True, "one_job_at_a_time": True,
                        "media_requires_rights_record": True, "publish_requires_confirmation": True},
              "scenes": scenes}
    output = target / "05-timeline" / "storyboard.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


def _metadata_text(metadata: dict, key: str) -> str:
    value = str((metadata.get(key) or {}).get("value") or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def media_candidates(args) -> int:
    target = project_path(args.project)
    storyboard_path = target / "05-timeline" / "storyboard.json"
    queries_path = target / "04-midia" / "buscas-midia.json"
    if not storyboard_path.is_file() or not queries_path.is_file():
        raise FileNotFoundError("Crie o storyboard e o arquivo 04-midia/buscas-midia.json primeiro.")
    board = _load_json(storyboard_path)
    queries = _load_json(queries_path)
    allowed = ("cc0", "public domain", "cc by", "cc-by", "cc by-sa", "cc-by-sa")
    results = []
    for scene in board.get("scenes", []):
        scene_queries = queries.get(str(scene.get("order")), [])
        scene_result = {"order": scene.get("order"), "queries": scene_queries, "candidates": []}
        seen = set()
        for search in scene_queries:
            params = {
                "action": "query", "format": "json", "formatversion": "2",
                "generator": "search", "gsrsearch": f"filetype:bitmap {search}",
                "gsrnamespace": "6", "gsrlimit": str(args.limit),
                "prop": "imageinfo", "iiprop": "url|mime|dimensions|extmetadata",
                "iiurlwidth": "1920",
                "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Credit|ImageDescription|UsageTerms",
            }
            url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
            data = request_json(url, timeout=45)
            time.sleep(1)
            for page in (data.get("query") or {}).get("pages", []):
                info = (page.get("imageinfo") or [{}])[0]
                metadata = info.get("extmetadata") or {}
                license_name = _metadata_text(metadata, "LicenseShortName")
                if not any(item in license_name.lower() for item in allowed):
                    continue
                source_url = str(info.get("descriptionurl") or "")
                if not source_url or source_url in seen:
                    continue
                seen.add(source_url)
                scene_result["candidates"].append({
                    "title": page.get("title"),
                    "preview_url": info.get("thumburl") or info.get("url"),
                    "original_url": info.get("url"),
                    "source_page": source_url,
                    "mime": info.get("mime"),
                    "width": info.get("width"), "height": info.get("height"),
                    "license": license_name,
                    "license_url": _metadata_text(metadata, "LicenseUrl"),
                    "author": _metadata_text(metadata, "Artist"),
                    "credit": _metadata_text(metadata, "Credit"),
                    "description": _metadata_text(metadata, "ImageDescription"),
                    "status": "pending-human-review",
                })
        results.append(scene_result)
    output = target / "04-midia" / "candidatos-wikimedia.json"
    output.write_text(json.dumps({"created_at": now(), "source": COMMONS_API, "scenes": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


def animatic(args) -> int:
    target = project_path(args.project)
    voice_dir = target / "03-voz"
    media_dir = target / "04-midia" / "animatic"
    timeline_dir = target / "05-timeline"
    media_dir.mkdir(parents=True, exist_ok=True)
    titles = [
        "AS 5 NOTÍCIAS DA SEMANA", "DÓLAR E IBOVESPA", "QUÍMICOS E SAÚDE",
        "CÚPULA DE SHENZHEN", "RESISTÊNCIA ANTIMICROBIANA", "TENSÃO NO GOLFO",
        "O QUE MUDA AGORA?",
    ]
    scene_files = []
    durations = []
    font = "C\\:/Windows/Fonts/arialbd.ttf"
    for index, title in enumerate(titles, 1):
        audio = voice_dir / f"narracao-{index:02d}.wav"
        if not audio.is_file():
            raise FileNotFoundError(audio)
        scene = media_dir / f"cena-{index:02d}.mp4"
        filter_graph = (
            "drawbox=x=120:y=350:w=1680:h=380:color=black@0.48:t=fill,"
            f"drawtext=fontfile='{font}':text='{title}':fontcolor=white:fontsize=76:"
            "x=(w-text_w)/2:y=(h-text_h)/2-35,"
            f"drawtext=fontfile='{font}':text='CENA {index}/7 - mídia em revisão de licença':"
            "fontcolor=0x69d2ff:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2+80"
        )
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=0x0b1020:s=1920x1080:r=30",
            "-i", str(audio), "-vf", filter_graph, "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest",
            "-movflags", "+faststart", str(scene),
        ]
        completed = subprocess.run(command, text=True, capture_output=True, timeout=900)
        if completed.returncode or not scene.is_file():
            raise RuntimeError(completed.stderr.strip() or f"Falha ao gerar a cena {index}.")
        metadata = probe(scene)
        duration = float(metadata["format"]["duration"])
        scene_files.append(scene)
        durations.append(duration)

    manifest = media_dir / "cenas-concat.txt"
    manifest.write_text("\n".join(f"file '{path.as_posix()}'" for path in scene_files) + "\n", encoding="utf-8")
    preview = target / "06-revisao" / "animatic-canal-noticias.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
         "-safe", "0", "-i", str(manifest), "-c", "copy", "-movflags", "+faststart", str(preview)],
        check=True, timeout=900,
    )

    root = ET.Element("fcpxml", {"version": "1.11"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", {
        "id": "r1", "name": "FFVideoFormat1080p30", "width": "1920", "height": "1080",
        "frameDuration": "1/30s", "colorSpace": "1-1-1 (Rec. 709)",
    })
    for index, (scene, duration) in enumerate(zip(scene_files, durations), 2):
        ticks = round(duration * 30)
        asset = ET.SubElement(resources, "asset", {
            "id": f"r{index}", "name": scene.stem, "start": "0s", "duration": f"{ticks}/30s",
            "hasVideo": "1", "hasAudio": "1", "format": "r1", "audioSources": "1", "audioChannels": "2",
        })
        ET.SubElement(asset, "media-rep", {"kind": "original-media", "src": scene.as_uri()})
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "Ollama Video Studio"})
    project = ET.SubElement(event, "project", {"name": "Canal Dark - Animatic"})
    spine = ET.SubElement(ET.SubElement(project, "sequence", {
        "tcStart": "0s", "format": "r1", "tcFormat": "NDF", "audioLayout": "stereo", "audioRate": "48k",
    }), "spine")
    offset = 0
    for index, duration in enumerate(durations, 2):
        ticks = round(duration * 30)
        ET.SubElement(spine, "asset-clip", {
            "ref": f"r{index}", "name": titles[index - 2], "offset": f"{offset}/30s",
            "start": "0s", "duration": f"{ticks}/30s", "tcFormat": "NDF",
        })
        offset += ticks
    ET.indent(root, space="  ")
    fcpxml = timeline_dir / "canal-noticias-animatic.fcpxml"
    ET.ElementTree(root).write(fcpxml, encoding="utf-8", xml_declaration=True)
    print(preview)
    print(fcpxml)
    return 0


def record_voice(args) -> int:
    target = project_path(args.project) / "03-voz"
    if not target.is_dir():
        raise FileNotFoundError("Crie o projeto primeiro.")
    output = target / "referencia-voz-biel.wav"
    recorder = ROOT / "src" / "voice_recorder.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = pythonw if pythonw.is_file() else Path(sys.executable)
    subprocess.Popen([str(launcher), str(recorder), "--output", str(output)])
    print(output)
    return 0


def set_voice(args) -> int:
    target = project_path(args.project) / "03-voz"
    if not target.is_dir():
        raise FileNotFoundError("Crie o projeto primeiro.")
    profiles = request_json(f"{VOICE_URL}/profiles")
    profile = next((item for item in profiles if item.get("id") == args.profile), None)
    if not profile:
        raise ValueError(f"Perfil de voz não encontrado no VoiceStudio: {args.profile}")
    record = {
        "profile_id": profile["id"],
        "name": profile.get("name"),
        "engine": args.engine,
        "language": args.language,
        "reference_audio": str(target / "referencia-voz-biel-clone.wav"),
        "reference_text": args.reference_text or profile.get("ref_text") or "",
        "authorization": "owner-authorized-local-voice-clone",
        "configured_at": now(),
    }
    output = target / "voice-profile.json"
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


def dark_news(args) -> int:
    """Advance the local weekly-news project to the next human review gate."""
    target = project_path(args.project)
    if not target.exists():
        new_project(argparse.Namespace(name=args.project, channel="noticias"))
    pool_path = target / "01-fontes" / "editorial-pool.json"
    if not pool_path.exists():
        today = datetime.now().astimezone().date()
        monday = today - timedelta(days=today.weekday())
        init_weekly_news(argparse.Namespace(project=args.project, week_start=monday.isoformat()))

    date_label = datetime.now().astimezone().strftime("%d/%m/%Y")
    queries = [
        f"notícias Brasil política economia impacto {date_label}",
        f"notícias mundo geopolítica impacto {date_label}",
        f"notícias ciência tecnologia inteligência artificial {date_label}",
        f"notícias saúde clima meio ambiente {date_label}",
        f"acontecimentos mais repercutidos da semana Brasil mundo {date_label}",
    ]
    for query in queries:
        collect_news(argparse.Namespace(project=args.project, query=query, limit=args.per_query))
    rank_news(argparse.Namespace(project=args.project, count=5))
    draft(
        argparse.Namespace(
            project=args.project,
            brief=(
                "Vídeo jornalístico de 8 a 15 minutos com as cinco pautas de maior impacto da semana. "
                "Tom humano, claro e sóbrio; explique contexto, relevância e consequência. "
                "Separe as cinco notícias e sinalize qualquer fato que ainda precise de confirmação."
            ),
            max_sources=15,
        )
    )
    storyboard(argparse.Namespace(project=args.project))

    reference = target / "03-voz" / "referencia-voz-biel.wav"
    if not reference.is_file() and not args.no_recorder:
        record_voice(argparse.Namespace(project=args.project))
    status = {
        "schema": "ollama-video-run.v1",
        "updated_at": now(),
        "project": args.project,
        "completed": ["news_collection", "preliminary_ranking", "script_draft", "storyboard"],
        "voice_reference": str(reference) if reference.is_file() else "recording_requested",
        "blocked_until_review": [
            "confirm facts with independent or primary sources",
            "approve script",
            "register the authorized voice reference in VoiceStudio",
            "record media rights before downloading or rendering third-party material",
        ],
        "next_action": "review-script-and-sources",
        "automatic_publish": False,
    }
    status_path = target / "STATUS.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(status_path)
    return 0


def narrate(args) -> int:
    target = project_path(args.project) / "03-voz"
    if not target.is_dir():
        raise FileNotFoundError("Crie o projeto primeiro.")
    profile_path = target / "voice-profile.json"
    saved_profile = _load_json(profile_path) if profile_path.is_file() else {}
    voice = args.voice or saved_profile.get("profile_id") or saved_profile.get("id")
    if not voice:
        raise RuntimeError("Cadastre a referência da sua voz antes de narrar.")
    out = target / args.output
    if args.engine == "audiocpp-dots":
        reference = Path(saved_profile.get("reference_audio") or target / "referencia-voz-biel-clone.wav")
        if not AUDIOCPP_CLI.is_file() or not DOTS_MODEL.is_file() or not reference.is_file():
            raise FileNotFoundError("Motor dots.tts, modelo ou referência da voz não encontrado.")
        try:
            request_json(f"{OLLAMA_URL}/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=30)
        except Exception:
            pass
        sentences = re.split(r"(?<=[.!?;:])\s+", args.text.strip())
        chunks = []
        for sentence in sentences:
            words = sentence.split()
            while words:
                chunk_words = []
                while words and len(" ".join(chunk_words + [words[0]])) <= 220:
                    chunk_words.append(words.pop(0))
                if not chunk_words:
                    chunk_words.append(words.pop(0))
                chunk = " ".join(chunk_words).strip()
                if chunk:
                    chunks.append(chunk)
        if not chunks:
            raise RuntimeError("O texto da narração está vazio.")

        raw_parts = []
        for index, chunk in enumerate(chunks, 1):
            raw = out if len(chunks) == 1 else target / f".{out.stem}-parte-{index:03d}.wav"
            command = [
                str(AUDIOCPP_CLI), "--task", "tts", "--family", "dots_tts",
                "--model", str(DOTS_MODEL), "--backend", "vulkan", "--device", "1",
                "--threads", "1", "--text", chunk, "--voice-ref", str(reference),
                "--language", args.language, "--out", str(raw),
            ]
            reference_text = str(saved_profile.get("reference_text") or "").strip()
            if reference_text:
                command[command.index("--language"):command.index("--language")] = [
                    "--reference-text", reference_text,
                ]
            completed = subprocess.run(command, text=True, capture_output=True, timeout=900)
            if completed.returncode or not raw.is_file():
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Falha ao gerar a voz.")
            raw_parts.append(raw)

        if len(raw_parts) > 1:
            concat_file = target / f".{out.stem}-partes.txt"
            concat_file.write_text(
                "\n".join(f"file '{path.as_posix()}'" for path in raw_parts) + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(out)],
                check=True, timeout=300,
            )
            concat_file.unlink(missing_ok=True)
            for raw in raw_parts:
                raw.unlink(missing_ok=True)
        normalized = out.with_name(f"{out.stem}-normalized.wav")
        subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out),
             "-af", "highpass=f=65,lowpass=f=15000,equalizer=f=3200:t=q:w=0.8:g=-1.8,"
                    "acompressor=threshold=0.125:ratio=2:attack=15:release=180:makeup=1.25,"
                    "loudnorm=I=-18:LRA=7:TP=-2",
             "-ar", "48000", "-ac", "1", str(normalized)],
            check=True, timeout=300,
        )
        normalized.replace(out)
        print(out)
        return 0
    payload = {
        "model": args.engine, "input": args.text, "voice": voice,
        "response_format": "wav", "language": args.language, "speed": args.speed,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{VOICE_URL}/v1/audio/speech", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as response:
        audio = response.read()
    if not audio.startswith(b"RIFF"):
        raise RuntimeError("O VoiceStudio não retornou um WAV válido.")
    out.write_bytes(audio)
    print(out)
    return 0


def narrate_script(args) -> int:
    target = project_path(args.project)
    script_path = target / "02-roteiro" / "rascunho-com-fontes.json"
    if not script_path.is_file():
        raise FileNotFoundError("Crie o roteiro antes da narração.")
    script = _load_json(script_path)
    parts = [str(script.get("opening") or "").strip()]
    parts.extend(str(item.get("narration") or "").strip() for item in script.get("segments", []))
    parts.append(str(script.get("closing") or "").strip())
    parts = [text for text in parts if text]
    if not parts:
        raise RuntimeError("O roteiro não contém texto para narrar.")

    voice_dir = target / "03-voz"
    generated = []
    for index, text in enumerate(parts, 1):
        filename = f"narracao-{index:02d}.wav"
        narrate(argparse.Namespace(
            project=args.project, text=text, voice=None, engine=args.engine,
            language=args.language, speed=1.0, output=filename,
        ))
        generated.append(voice_dir / filename)

    silence = voice_dir / "pausa-035ms.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=48000:cl=mono", "-t", "0.35", str(silence)],
        check=True, timeout=30,
    )
    concat_file = voice_dir / "narracao-concat.txt"
    concat_lines = []
    for index, path in enumerate(generated):
        concat_lines.append(f"file '{path.as_posix()}'")
        if index < len(generated) - 1:
            concat_lines.append(f"file '{silence.as_posix()}'")
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    output = voice_dir / args.output
    subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat_file), "-af", "loudnorm=I=-18:LRA=7:TP=-2", "-ar", "48000", "-ac", "1", str(output)],
        check=True, timeout=600,
    )
    print(output)
    return 0


def silence(args) -> int:
    source = Path(args.input).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    target = project_path(args.project) / "05-timeline"
    if not target.is_dir():
        raise FileNotFoundError("Crie o projeto primeiro.")
    editor = auto_editor()
    if not editor:
        raise FileNotFoundError("Auto-Editor não encontrado.")
    output = target / f"{source.stem}-sem-silencios.fcpxml"
    command = [str(editor), str(source), "--margin", args.margin, "--export", "resolve", "--output", str(output), "--no-open", "--progress", "none"]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    log = {"created_at": now(), "input": str(source), "output": str(output), "command": command, "original_preserved": True}
    (target / f"{source.stem}-sem-silencios.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def transcribe_command(args) -> int:
    source = Path(args.input).expanduser().resolve()
    target = project_path(args.project) / "04-midia"
    if not target.is_dir():
        raise FileNotFoundError("Crie o projeto primeiro.")
    model = Path(args.model).expanduser().resolve()
    segments = transcribe_media(source, model, args.language, args.gpu)
    output = target / f"{source.stem}-transcricao.json"
    output.write_text(json.dumps({"source": str(source), "created_at": now(), "segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


HIGHLIGHTS_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"}, "end": {"type": "number"},
                    "title": {"type": "string"}, "reason": {"type": "string"},
                    "hook": {"type": "string"}, "score": {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["start", "end", "title", "reason", "hook", "score"],
            },
        },
        "editor_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["clips", "editor_notes"],
}


def highlights(args) -> int:
    source = Path(args.input).expanduser().resolve()
    target = project_path(args.project)
    media = target / "04-midia"
    timeline = target / "05-timeline"
    transcript_path = media / f"{source.stem}-transcricao.json"
    if transcript_path.is_file() and not getattr(args, "retranscribe", False):
        transcript = _load_json(transcript_path)
    else:
        segments = transcribe_media(source, Path(args.model).expanduser().resolve(), args.language, args.gpu)
        transcript = {"source": str(source), "created_at": now(), "segments": segments}
        transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    # Vídeos longos são avaliados em blocos para não truncar a saída estruturada do modelo.
    blocks: dict[int, list[dict]] = {}
    for segment in transcript["segments"]:
        blocks.setdefault(int(float(segment["start"]) // 240), []).append(
            {"start": segment["start"], "end": segment["end"], "text": segment["text"]}
        )
    proposed: list[dict] = []
    editor_notes: list[str] = []
    for block_number, compact in sorted(blocks.items()):
        prompt = (
            "Você é editor de vídeos curtos. A partir deste bloco, sugira no máximo dois trechos contínuos "
            "que façam sentido isoladamente, com gancho, desenvolvimento e conclusão. Use somente tempos presentes "
            "na transcrição; não invente falas. "
            f"Cada trecho deve ter entre {args.min_duration} e {args.max_duration} segundos. "
            "Priorize reação forte, revelação, conflito, humor ou explicação memorável. "
            "Exclua propaganda, patrocinador, preço, cupom, pedido de clique, inscrição ou compra. "
            "Os resultados são sugestões e precisam de revisão humana.\n"
            f"Bloco {block_number + 1}: {json.dumps(compact, ensure_ascii=False)}"
        )
        response = request_json(f"{OLLAMA_URL}/api/generate", {
            "model": MODEL, "prompt": prompt, "stream": False, "format": HIGHLIGHTS_SCHEMA,
            "think": False, "options": {"temperature": 0.15, "num_ctx": 8192, "num_predict": 1200},
        }, timeout=300)
        try:
            partial = json.loads(response["response"])
        except json.JSONDecodeError:
            editor_notes.append(f"O bloco {block_number + 1} retornou JSON incompleto e foi ignorado.")
            continue
        proposed.extend(partial.get("clips", []))
        editor_notes.extend(partial.get("editor_notes", []))
    metadata = probe(source)
    duration = float(metadata.get("format", {}).get("duration") or 0)
    valid = []
    ranked = sorted(proposed, key=lambda item: (-float(item.get("score", 0)), float(item["start"])))
    for clip in ranked:
        start, end = max(0.0, float(clip["start"])), min(duration, float(clip["end"]))
        length = end - start
        excerpt = " ".join(
            segment["text"].lower() for segment in transcript["segments"]
            if float(segment["start"]) < end and float(segment["end"]) > start
        )
        ad_markers = (" reais", "link", "clique", "cupom", "de graça", "compre", "inscreva", "patrocin", "promoção")
        if sum(marker in excerpt for marker in ad_markers) >= 2:
            editor_notes.append(f"Trecho {start:.1f}s–{end:.1f}s rejeitado por sinais de propaganda/CTA.")
            continue
        if args.min_duration <= length <= args.max_duration and not any(start < old["end"] and end > old["start"] for old in valid):
            valid.append({**clip, "score": min(100, max(0, float(clip.get("score", 0)))), "start": round(start, 3), "end": round(end, 3), "duration": round(length, 3)})
        if len(valid) >= args.count:
            break
    if not valid:
        raise RuntimeError("O modelo não devolveu trechos válidos; o vídeo e a transcrição foram preservados.")
    valid.sort(key=lambda item: item["start"])
    plan = {"source": str(source), "created_at": now(), "status": "needs_human_review", "clips": valid, "editor_notes": editor_notes}
    plan_path = timeline / f"{source.stem}-melhores-momentos.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    fps_text = next((s.get("r_frame_rate") for s in metadata.get("streams", []) if s.get("codec_type") == "video"), "30/1")
    fps = max(1, round(int(fps_text.split("/")[0]) / int(fps_text.split("/")[1])))
    edl_path = timeline / f"{source.stem}-melhores-momentos.edl"
    write_cmx3600(source, valid, edl_path, fps)
    fcpxml_path = timeline / f"{source.stem}-melhores-momentos.fcpxml"
    write_fcpxml(source, valid, fcpxml_path, metadata)
    print(json.dumps({"plan": str(plan_path), "edl": str(edl_path), "fcpxml": str(fcpxml_path), "clips": len(valid)}, ensure_ascii=False))
    return 0


def render_highlights(args) -> int:
    target = project_path(args.project)
    timeline = target / "05-timeline"
    review = target / "06-revisao"
    plan_path = Path(args.plan).expanduser().resolve() if args.plan else next(
        iter(sorted(timeline.glob("*-melhores-momentos.json"), key=lambda path: path.stat().st_mtime, reverse=True)), None
    )
    if not plan_path or not plan_path.is_file():
        raise FileNotFoundError("Nenhum plano de melhores momentos foi encontrado.")
    plan = _load_json(plan_path)
    source = Path(plan["source"])
    clips = plan.get("clips", [])
    if not source.is_file() or not clips:
        raise RuntimeError("O plano não tem fonte e trechos válidos.")
    filters = []
    concat_inputs = []
    for index, clip in enumerate(clips):
        start, end = float(clip["start"]), float(clip["end"])
        filters.extend([
            f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{index}]",
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{index}]",
        ])
        concat_inputs.append(f"[v{index}][a{index}]")
    filters.append(f"{''.join(concat_inputs)}concat=n={len(clips)}:v=1:a=1[vout][aout]")
    output = review / f"{source.stem}-melhores-momentos-preview.mp4"
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", str(source),
        "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=3600)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "Falha ao renderizar a prévia.")
    report = {"created_at": now(), "source_plan": str(plan_path), "output": str(output), "clips": len(clips), "status": "needs_human_review"}
    (review / f"{output.stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


def render_shorts(args) -> int:
    target = project_path(args.project)
    timeline = target / "05-timeline"
    review = target / "06-revisao"
    plan_path = Path(args.plan).expanduser().resolve() if args.plan else next(
        iter(sorted(timeline.glob("*-melhores-momentos.json"), key=lambda path: path.stat().st_mtime, reverse=True)), None
    )
    if not plan_path or not plan_path.is_file():
        raise FileNotFoundError("Nenhum plano de melhores momentos foi encontrado.")
    plan = _load_json(plan_path)
    source = Path(plan["source"])
    transcript_path = target / "04-midia" / f"{source.stem}-transcricao.json"
    if not source.is_file() or not transcript_path.is_file():
        raise FileNotFoundError("O vídeo original ou a transcrição local não foi encontrado.")
    segments = _load_json(transcript_path)["segments"]
    previous_report = review / "shorts-render.json"
    if previous_report.is_file():
        for item in _load_json(previous_report).get("outputs", []):
            for key in ("video", "captions", "focus_commands"):
                old = Path(item.get(key, ""))
                if old.parent == review and old.name.startswith("short-") and old.suffix.lower() in {".mp4", ".srt", ".ass", ".txt"}:
                    old.unlink(missing_ok=True)
    audio_filter = (
        "highpass=f=70,lowpass=f=15500,equalizer=f=250:t=q:w=1:g=-1.5,"
        "equalizer=f=3200:t=q:w=1.2:g=1.5,"
        "acompressor=threshold=-18dB:ratio=2:attack=20:release=250:makeup=1.5dB,"
        "loudnorm=I=-14:TP=-2:LRA=7"
    )
    outputs = []
    for index, clip in enumerate(plan.get("clips", []), 1):
        stem = f"short-{index:02d}"
        captions = review / f"{stem}.ass"
        write_clip_ass(segments, float(clip["start"]), float(clip["end"]), captions, title=clip.get("title"))
        focus_commands = review / f"{stem}-focus.txt"
        focus = write_focus_commands(source, float(clip["start"]), float(clip["end"]), focus_commands)
        output = review / f"{stem}.mp4"
        video_filter = (
            f"sendcmd=f='{focus_commands.name}',crop@focus={focus['crop_width']}:{focus['source_height']}:"
            f"x={(focus['source_width'] - focus['crop_width']) // 2}:y=0,"
            "scale=1080:1920:flags=lanczos,fps=30,"
            f"ass=filename='{captions.name}'"
        )
        duration = float(clip["end"]) - float(clip["start"])
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-y", "-ss", str(clip["start"]), "-i", str(source),
            "-t", str(duration), "-vf", video_filter,
            "-af", audio_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(output),
        ]
        completed = subprocess.run(command, cwd=review, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=3600)
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or f"Falha ao renderizar {stem}.")
        outputs.append({"video": str(output), "captions": str(captions), "focus_commands": str(focus_commands), "focus": focus, "title": clip.get("title"), "status": "needs_human_review"})
    report = {
        "created_at": now(), "source_plan": str(plan_path), "layout": "tracked-subject-9x16",
        "camera_motion": "continuous-eased-pan-30fps", "title_popup": "0.2s-3.2s, fade in/out",
        "caption_safe_area": "1080x1920, bottom margin 510px",
        "audio_processing": {"profile": "dialogue-mild-v1", "filter": audio_filter, "noise_reduction": "not applied without noise evidence"},
        "outputs": outputs, "rights_review_required": True,
    }
    report_path = review / "shorts-render.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "shorts": outputs}, ensure_ascii=False))
    return 0


def auto_highlights(args) -> int:
    highlights(args)
    render_args = argparse.Namespace(project=args.project, plan=None)
    render_highlights(render_args)
    render_shorts(render_args)
    print(json.dumps({
        "project": str(project_path(args.project)),
        "state": "ready_for_human_review",
        "next": "Revise os cortes, as legendas e os direitos antes de aprovar.",
    }, ensure_ascii=False))
    return 0


def master_audio_command(args) -> int:
    source = Path(args.input).expanduser().resolve()
    target = project_path(args.project) / "03-voz"
    profile = _load_json(ROOT / "config/audio/master-web.json")
    output = target / args.output
    report = master_audio_file(source, output, profile)
    report.update({"created_at": now(), "source": str(source), "original_preserved": True})
    report_path = target / f"{output.stem}-masterizacao.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"audio": str(output), "report": str(report_path)}, ensure_ascii=False))
    return 0


def qc_command(args) -> int:
    source = Path(args.input).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    target = project_path(args.project) / "06-revisao"
    quality_path = ROOT / "config/quality" / f"{args.profile}.json"
    if not quality_path.is_file():
        raise FileNotFoundError(f"Perfil de qualidade desconhecido: {args.profile}")
    report = quality_report(source, _load_json(quality_path), _load_json(ROOT / "config/audio/master-web.json"))
    report["created_at"] = now()
    output = target / f"{source.stem}-qc.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "automatic_passed": report["automatic_passed"]}, ensure_ascii=False))
    return 0 if report["automatic_passed"] else 1


def review_video_command(args) -> int:
    source = Path(args.input).expanduser().resolve()
    target = project_path(args.project) / "06-revisao" / source.stem
    report = review_video(source, target, sample_count=args.samples)
    report["created_at"] = now()
    Path(report["report"]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": report["report"],
        "contact_sheet": report["contact_sheet"],
        "metrics": report["metrics"],
        "next": "Inspecione a folha de revisão antes de aprovar o vídeo.",
    }, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ollama-video", description="Orquestrador local de vídeo")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("doctor"); d.set_defaults(func=doctor)
    n = sub.add_parser("new"); n.add_argument("--name", required=True); n.add_argument("--channel", default="noticias"); n.set_defaults(func=new_project)
    i = sub.add_parser("init-weekly-news"); i.add_argument("--project", required=True); i.add_argument("--week-start", required=True); i.set_defaults(func=init_weekly_news)
    q = sub.add_parser("plan"); q.add_argument("--project", required=True); q.add_argument("--brief", required=True); q.set_defaults(func=plan)
    r = sub.add_parser("research"); r.add_argument("--project", required=True); r.add_argument("--query", required=True); r.add_argument("--limit", type=int, default=8, choices=range(1, 21)); r.set_defaults(func=research)
    c = sub.add_parser("collect-news"); c.add_argument("--project", required=True); c.add_argument("--query", required=True); c.add_argument("--limit", type=int, default=20, choices=range(1, 21)); c.set_defaults(func=collect_news)
    k = sub.add_parser("rank-news"); k.add_argument("--project", required=True); k.add_argument("--count", type=int, default=5, choices=range(1, 11)); k.set_defaults(func=rank_news)
    w = sub.add_parser("draft"); w.add_argument("--project", required=True); w.add_argument("--brief", required=True); w.add_argument("--max-sources", type=int, default=8, choices=range(2, 16)); w.set_defaults(func=draft)
    b = sub.add_parser("storyboard"); b.add_argument("--project", required=True); b.set_defaults(func=storyboard)
    f = sub.add_parser("media-candidates"); f.add_argument("--project", required=True); f.add_argument("--limit", type=int, default=5, choices=range(1, 11)); f.set_defaults(func=media_candidates)
    g = sub.add_parser("animatic"); g.add_argument("--project", required=True); g.set_defaults(func=animatic)
    o = sub.add_parser("record-voice"); o.add_argument("--project", required=True); o.set_defaults(func=record_voice)
    u = sub.add_parser("set-voice"); u.add_argument("--project", required=True); u.add_argument("--profile", required=True); u.add_argument("--engine", default="audiocpp-dots"); u.add_argument("--language", default="pt-BR"); u.add_argument("--reference-text"); u.set_defaults(func=set_voice)
    e = sub.add_parser("dark-news"); e.add_argument("--project", default="canal-noticias"); e.add_argument("--per-query", type=int, default=10, choices=range(5, 21)); e.add_argument("--no-recorder", action="store_true"); e.set_defaults(func=dark_news)
    v = sub.add_parser("narrate"); v.add_argument("--project", required=True); v.add_argument("--text", required=True); v.add_argument("--voice"); v.add_argument("--engine", default="audiocpp-dots"); v.add_argument("--language", default="pt-BR"); v.add_argument("--speed", type=float, default=1.0); v.add_argument("--output", default="narracao.wav"); v.set_defaults(func=narrate)
    j = sub.add_parser("narrate-script"); j.add_argument("--project", required=True); j.add_argument("--engine", default="audiocpp-dots"); j.add_argument("--language", default="pt-BR"); j.add_argument("--output", default="narracao-completa.wav"); j.set_defaults(func=narrate_script)
    s = sub.add_parser("silence"); s.add_argument("--project", required=True); s.add_argument("--input", required=True); s.add_argument("--margin", default="0.2s"); s.set_defaults(func=silence)
    t = sub.add_parser("transcribe"); t.add_argument("--project", required=True); t.add_argument("--input", required=True); t.add_argument("--model", default=str(WHISPER_MODEL)); t.add_argument("--language", default="pt"); t.add_argument("--gpu", action="store_true"); t.set_defaults(func=transcribe_command)
    h = sub.add_parser("highlights"); h.add_argument("--project", required=True); h.add_argument("--input", required=True); h.add_argument("--model", default=str(WHISPER_MODEL)); h.add_argument("--language", default="pt"); h.add_argument("--gpu", action="store_true"); h.add_argument("--retranscribe", action="store_true"); h.add_argument("--count", type=int, default=5, choices=range(1, 11)); h.add_argument("--min-duration", type=int, default=25); h.add_argument("--max-duration", type=int, default=70); h.set_defaults(func=highlights)
    z = sub.add_parser("render-highlights"); z.add_argument("--project", required=True); z.add_argument("--plan"); z.set_defaults(func=render_highlights)
    y = sub.add_parser("render-shorts"); y.add_argument("--project", required=True); y.add_argument("--plan"); y.set_defaults(func=render_shorts)
    a = sub.add_parser("auto-highlights"); a.add_argument("--project", required=True); a.add_argument("--input", required=True); a.add_argument("--model", default=str(WHISPER_MODEL)); a.add_argument("--language", default="pt"); a.add_argument("--gpu", action="store_true"); a.add_argument("--retranscribe", action="store_true"); a.add_argument("--count", type=int, default=5, choices=range(1, 11)); a.add_argument("--min-duration", type=int, default=25); a.add_argument("--max-duration", type=int, default=70); a.set_defaults(func=auto_highlights)
    m = sub.add_parser("master-audio"); m.add_argument("--project", required=True); m.add_argument("--input", required=True); m.add_argument("--output", default="narracao-master.wav"); m.set_defaults(func=master_audio_command)
    x = sub.add_parser("qc"); x.add_argument("--project", required=True); x.add_argument("--input", required=True); x.add_argument("--profile", default="youtube-1080p", choices=("youtube-1080p", "shorts-1080x1920")); x.set_defaults(func=qc_command)
    vr = sub.add_parser("review-video"); vr.add_argument("--project", required=True); vr.add_argument("--input", required=True); vr.add_argument("--samples", type=int, default=12, choices=range(6, 25)); vr.set_defaults(func=review_video_command)
    return p


def main() -> int:
    try:
        args = parser().parse_args()
        return args.func(args)
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, urllib.error.URLError) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

