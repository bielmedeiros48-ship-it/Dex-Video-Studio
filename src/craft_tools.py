from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess


FILMCRAFT_CANDIDATES = (
    Path(os.environ.get("DEX_FILMCRAFT_CLI", "")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "FilmCraft/filmcraft-cli.exe",
    Path(shutil.which("filmcraft-cli") or ""),
)
PHOTOCRAFT_CANDIDATES = (
    Path(os.environ.get("DEX_PHOTOCRAFT_CLI", "")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PhotoCraft/photocraft-cli.exe",
    Path(shutil.which("photocraft-cli") or ""),
)


def _first_file(candidates: tuple[Path, ...]) -> Path | None:
    return next((path for path in candidates if str(path) and path.is_file()), None)


def filmcraft_cli() -> Path | None:
    return _first_file(FILMCRAFT_CANDIDATES)


def photocraft_cli() -> Path | None:
    return _first_file(PHOTOCRAFT_CANDIDATES)


def _environment(home: Path) -> dict[str, str]:
    allowed = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP")
    environment = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    environment.update({"HOME": str(home), "USERPROFILE": str(home)})
    return environment


def _run_json(command: list[str], home: Path, timeout: int = 120) -> dict:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_environment(home),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or f"A ferramenta terminou com código {completed.returncode}.")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("A ferramenta não retornou JSON válido.") from error


def versions(home: Path) -> dict[str, dict[str, str | bool | None]]:
    result: dict[str, dict[str, str | bool | None]] = {}
    for name, executable in (("filmcraft", filmcraft_cli()), ("photocraft", photocraft_cli())):
        version = None
        if executable:
            completed = subprocess.run(
                [str(executable), "--version"],
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                env=_environment(home),
            )
            if completed.returncode == 0:
                version = completed.stdout.strip()
        result[name] = {"available": bool(executable), "path": str(executable) if executable else None, "version": version}
    return result


def probe_media(source: Path, home: Path) -> dict:
    executable = filmcraft_cli()
    if not executable:
        raise FileNotFoundError("filmcraft-cli não foi encontrado.")
    return _run_json([str(executable), "probe", str(source)], home)


def inspect_image(source: Path, home: Path, detail: bool = False) -> dict:
    executable = photocraft_cli()
    if not executable:
        raise FileNotFoundError("photocraft-cli não foi encontrado.")
    command = [str(executable), "info", str(source), "--compact"]
    if detail:
        command.append("--detail")
    return _run_json(command, home)


def create_filmcraft_timeline(source: Path, output: Path, home: Path) -> dict:
    executable = filmcraft_cli()
    if not executable:
        raise FileNotFoundError("filmcraft-cli não foi encontrado.")
    if output.exists():
        raise FileExistsError(f"A timeline já existe: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    building = output.with_name(f"{output.stem}.building.fcproj")
    if building.exists():
        raise FileExistsError(f"Existe uma construção incompleta: {building}")
    try:
        imported = _run_json([str(executable), "--save-as", str(building), "import", str(source)], home, timeout=900)
        items = imported.get("items") or []
        if len(items) != 1:
            raise RuntimeError("O FilmCraft não retornou exatamente um item importado.")
        media = probe_media(source, home)
        video = media.get("video") or {}
        frame_rate = video.get("frame_rate") or {}
        numerator = int(frame_rate.get("num") or 30)
        denominator = int(frame_rate.get("den") or 1)
        sequence = _run_json([
            str(executable), "--project", str(building), "--save", "exec", "file.newSequence",
            json.dumps({
                "name": "Dex Timeline",
                "width": int(video.get("width") or 1920),
                "height": int(video.get("height") or 1080),
                "fps": numerator / denominator,
                "video": 3,
                "audio": 3,
            }),
        ], home)
        placed = _run_json([
            str(executable), "--project", str(building), "--save", "exec", "timeline.place",
            json.dumps({
                "item": items[0], "track": "V1", "audioTrack": "A1", "seconds": 0,
                "insert": False, "video": True, "audio": True, "matchSequence": False,
            }),
        ], home)
        inspected = _run_json([str(executable), "--project", str(building), "inspect", "sequence"], home)
        building.replace(output)
        return {
            "project": str(output),
            "media_item": items[0],
            "sequence": sequence.get("sequence"),
            "clips": placed.get("clips", []),
            "settings": inspected.get("settings", {}),
        }
    except Exception:
        if building.exists():
            building.unlink()
        raise
