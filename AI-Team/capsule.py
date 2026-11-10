"""Enable, validate, carry away, and merge a Portable AI Team capsule."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


MARKER = "portable-ai-team-capsule-v1"
BLOCK_START = "<!-- portable-ai-team-capsule:start -->"
BLOCK_END = "<!-- portable-ai-team-capsule:end -->"
CAPSULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CAPSULE_ROOT.parent
PROJECT_MARKER = ".portable-ai-team.json"
ANCHOR_FILE = CAPSULE_ROOT / "胶囊根.txt"
DEFAULT_ANCHOR = "Portable-AI-Team"
STATE_DIR = CAPSULE_ROOT / "state"
MANIFEST_PATH = STATE_DIR / "installation.json"
LAST_REPORT_PATH = STATE_DIR / "last-operation.json"
TEAM_PATH = CAPSULE_ROOT / "AI-Team" / "team.json"
VERSION_PATH = CAPSULE_ROOT / "VERSION.json"
STATUS_PATH = CAPSULE_ROOT / "团队状态.json"
MEMORY_DIR = CAPSULE_ROOT / "AI-Team" / "memory"
LEDGER_PATH = MEMORY_DIR / "记忆账本.json"
MEMORY_STATE_PATH = STATE_DIR / "memory.json"
BRIDGES = (
    ("codex-agent", ".codex/agents/agent-b.toml", "bridges/codex/agent-b.toml"),
    ("codex-agent", ".codex/agents/agent-c.toml", "bridges/codex/agent-c.toml"),
    ("codex-agent", ".codex/agents/agent-d.toml", "bridges/codex/agent-d.toml"),
    ("trae-rule", ".trae/rules/portable-ai-team.md", "bridges/trae/portable-ai-team.md"),
    ("antigravity-rule", ".agents/rules/portable-ai-team.md", "bridges/antigravity/portable-ai-team.md"),
    ("antigravity-agent", ".agents/agents/agent-b/agent.md", "bridges/antigravity/agent-b.md"),
    ("antigravity-agent", ".agents/agents/agent-c/agent.md", "bridges/antigravity/agent-c.md"),
    ("antigravity-agent", ".agents/agents/agent-d/agent.md", "bridges/antigravity/agent-d.md"),
    ("workbuddy-rule", ".workbuddy/rules/portable-ai-team.md", "bridges/workbuddy/portable-ai-team.md"),
)
CLAUDE_BLOCK = (
    "<!-- portable-ai-team-capsule:start -->",
    "<!-- portable-ai-team-capsule:end -->",
)
INVISIBLE_CONTROLS = dict.fromkeys(map(ord, "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"))
QUOTE_PAIRS = (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’"))
MINIMUM_MERGE_VERSION = (2, 3, 0)


def configure_utf8_io() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="strict")


def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def capsule_anchor() -> str:
    """Read the stable capsule directory name from 胶囊根.txt (default Portable-AI-Team)."""
    if ANCHOR_FILE.is_file():
        for line in ANCHOR_FILE.read_text(encoding="utf-8-sig").splitlines():
            cleaned = line.translate(INVISIBLE_CONTROLS).strip()
            if cleaned:
                return cleaned
    return DEFAULT_ANCHOR


def capsule_relative(project_root: Path) -> str:
    """Return the capsule path relative to the project root, using forward slashes."""
    relative = os.path.relpath(CAPSULE_ROOT.resolve(), project_root.resolve())
    return Path(relative).as_posix()


def read_project_marker() -> dict | None:
    marker = PROJECT_ROOT / PROJECT_MARKER
    return load_json(marker) if marker.is_file() else None


def write_project_marker() -> None:
    save_json(
        PROJECT_ROOT / PROJECT_MARKER,
        {
            "schema": 1,
            "capsule_anchor": capsule_anchor(),
            "capsule_rel": capsule_relative(PROJECT_ROOT),
            "capsule_version": load_team_data().get("team_version", ""),
            "enabled_at": iso_now(),
        },
    )


def resolve_project_root(explicit: str | None = None) -> Path:
    """Resolve the business project root without guessing across unrelated directories."""
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not candidate.is_dir():
            raise ValueError(f"项目根目录不存在: {candidate}")
        return candidate

    # 1) A capsule marker in any ancestor wins; nearest ancestor first.
    for parent in (CAPSULE_ROOT, *CAPSULE_ROOT.parents):
        if (parent / PROJECT_MARKER).is_file():
            return parent.resolve()

    # 2) Structural markers: git repository or a bridge-capable project root.
    for parent in CAPSULE_ROOT.parents:
        if (parent / ".git").exists():
            return parent.resolve()
    for parent in CAPSULE_ROOT.parents:
        if (parent / "AGENTS.md").is_file() and ((parent / ".agents").exists() or (parent / ".codex").exists()):
            return parent.resolve()

    # 3) Legacy layout: the capsule is a direct child of the project root.
    #    Refuse this fallback for nested dist deployments, where the parent is
    #    a build-output directory and guessing would write bridges to the wrong place.
    if CAPSULE_ROOT.parent.name != "dist":
        return CAPSULE_ROOT.parent.resolve()

    raise ValueError(
        "无法确定项目根目录。请在启用时使用 --project <项目根>，或把项目文件夹拖到 双击启用团队.cmd 上。"
    )


def set_project_root(explicit: str | None = None) -> Path:
    global PROJECT_ROOT
    PROJECT_ROOT = resolve_project_root(explicit)
    return PROJECT_ROOT


def normalize_python_path(value: str) -> Path:
    candidate = value.translate(INVISIBLE_CONTROLS).strip()
    for opening, closing in QUOTE_PAIRS:
        if len(candidate) >= 2 and candidate.startswith(opening) and candidate.endswith(closing):
            candidate = candidate[len(opening):-len(closing)].strip()
            break
    path = Path(candidate)
    if not path.is_absolute():
        raise ValueError("Python 路径必须是绝对路径")
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"Python 路径不存在: {path}")
    return path


def configured_python_path(value: str | None = None) -> Path:
    if value is not None:
        return normalize_python_path(value)
    config = CAPSULE_ROOT / "Python路径.txt"
    if not config.is_file():
        raise ValueError("缺少 Python路径.txt")
    for line in config.read_text(encoding="utf-8-sig").splitlines():
        cleaned = line.translate(INVISIBLE_CONTROLS).strip()
        if cleaned:
            return normalize_python_path(cleaned)
    raise ValueError("Python路径.txt 中没有有效路径")


def bridge_source(relative: str, python_path: Path, capsule_rel: str) -> bytes:
    text = (Path(__file__).resolve().parent / relative).read_text(encoding="utf-8")
    text = text.replace("{{CAPSULE_PATH}}", capsule_rel)
    value = str(python_path)
    if relative.endswith(".toml"):
        value = value.replace("\\", "\\\\")
    return text.replace("{{PYTHON_PATH}}", value).encode("utf-8")


def agents_block(python_path: Path, capsule_rel: str = "Portable-AI-Team") -> bytes:
    """生成 AGENTS.md 团队区块。capsule_rel 是胶囊相对项目根的目录名（锚点，不带版本）。"""
    ai = f"{capsule_rel}/AI-Team"
    content = (
        f"{BLOCK_START}\n"
        "# Portable AI Team 桥接\n\n"
        f"团队主体位于 `{capsule_rel}/`。用户说“ZH，给我做一个……”时，"
        f"请读取 `{ai}/agents/AgentA.md`、相关策略与记忆索引。"
        "AgentA 通过根平台桥接委派 AgentB，并在返回后独立验收；最多自动返工 2 轮。\n"
        f"新建主要界面、整体改版或明确美化时，按团队 `{ai}/policies/ui-routing.md` 按需委派 AgentC 设计和视觉检查；纯后台及文字/颜色小改默认跳过 C。无子智能体时明确报告角色顺序模拟，不声称独立 C 或干净上下文隔离。\n"
        f"本项目默认 Python 解释器：`{python_path}`。AgentB 运行 Python、安装依赖和测试时优先使用该绝对路径。\n"
        "用户提出项目完成或准备带走团队时，AgentA 必须先把新且稳定的可复用经验压缩归纳到胶囊记忆，再提示双击带走；禁止收纳业务源码、密钥、原始日志、构建产物或项目依赖。\n"
        f"{BLOCK_END}\n"
    )
    return content.encode("utf-8")


def claude_block(python_path: Path, capsule_rel: str) -> bytes:
    text = (Path(__file__).resolve().parent / "bridges" / "claude" / "claude.md").read_text(encoding="utf-8")
    text = text.replace("{{CAPSULE_PATH}}", capsule_rel)
    return text.replace("{{PYTHON_PATH}}", str(python_path)).encode("utf-8")


def append_marked_block(target: Path, block: bytes) -> str:
    """Append a marked block to a markdown file (create if missing).
    Returns 'created' | 'appended' | 'merged' (identical block present)."""
    start, end = CLAUDE_BLOCK
    if target.exists():
        original = target.read_bytes()
        if start.encode() in original and end.encode() in original:
            if block in original:
                return "merged"
            conflicts = ["目标文件已含不受当前清单管理的团队标记区块，请先人工检查"]
            raise ValueError(conflicts[0])
        separator = b"\n" if original.endswith((b"\n", b"\r")) else b"\n\n"
        target.write_bytes(original + separator + block)
        return "appended"
    target.write_bytes(block)
    return "created"


def replace_marked_block(target: Path, block: bytes) -> str:
    """Create or replace only the managed block, preserving all project-owned content."""
    start, end = BLOCK_START.encode("utf-8"), BLOCK_END.encode("utf-8")
    if not target.exists():
        target.write_bytes(block)
        return "created"

    original = target.read_bytes()
    has_start = start in original
    has_end = end in original
    if has_start != has_end:
        raise ValueError("AGENTS.md 团队标记不完整（只有 start 或 end），请先人工检查")
    if has_start:
        start_index = original.index(start)
        end_index = original.index(end) + len(end)
        tail = original[end_index:]
        if tail.startswith(b"\r\n"):
            tail = tail[2:]
        elif tail.startswith(b"\n"):
            tail = tail[1:]
        replacement = original[:start_index] + block + tail
        if replacement == original:
            return "merged"
        target.write_bytes(replacement)
        return "replaced"

    separator = b"" if original.endswith((b"\n", b"\r")) else b"\n\n"
    target.write_bytes(original + separator + block)
    return "appended"


def add_created_parents(target: Path, created_dirs: list[str]) -> None:
    missing: list[Path] = []
    parent = target.parent
    while parent != PROJECT_ROOT and not parent.exists():
        missing.append(parent)
        parent = parent.parent
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in reversed(missing):
        relative = directory.relative_to(PROJECT_ROOT).as_posix()
        if relative not in created_dirs:
            created_dirs.append(relative)


def alternative_target(kind: str, target: Path, number: int = 1) -> Path:
    suffix = "" if number == 1 else f"-{number}"
    if kind == "codex-agent":
        return target.with_name(f"portable-ai-team-{target.stem}{suffix}.toml")
    if kind in {"trae-rule", "antigravity-rule", "workbuddy-rule"}:
        return target.with_name(f"portable-ai-team-capsule{suffix}.md")
    if kind == "antigravity-agent":
        return target.parent.parent / f"portable-ai-team-{target.parent.name}{suffix}" / "agent.md"
    raise ValueError(kind)


def choose_target(kind: str, target: Path, source: bytes, conflicts: list[str]) -> Path:
    if not target.exists():
        return target
    if target.is_file() and digest(target) == digest_bytes(source) and MARKER.encode() in source:
        return target
    conflicts.append(f"保留已有文件: {target.relative_to(PROJECT_ROOT).as_posix()}")
    number = 1
    while True:
        candidate = alternative_target(kind, target, number)
        if not candidate.exists():
            return candidate
        if candidate.is_file() and digest(candidate) == digest_bytes(source):
            return candidate
        conflicts.append(f"保留已有文件: {candidate.relative_to(PROJECT_ROOT).as_posix()}")
        number += 1


def load_team_data() -> dict:
    data = load_json(TEAM_PATH)
    if not isinstance(data, dict) or not data.get("team_version"):
        raise ValueError("AI-Team/team.json 缺失或无效")
    return data


def capsule_id() -> str:
    value = load_team_data().get("capsule_id")
    if not value:
        raise ValueError("AI-Team/team.json 缺少 capsule_id")
    return str(value)


def memory_file_map() -> dict[str, str]:
    result: dict[str, str] = {}
    if not MEMORY_DIR.exists():
        return result
    root = MEMORY_DIR.resolve()
    for path in sorted(p for p in MEMORY_DIR.rglob("*") if p.is_file() and p.suffix.lower() == ".md"):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            continue
        relative = path.relative_to(MEMORY_DIR).as_posix()
        if relative == "merge-inbox" or relative.startswith("merge-inbox/"):
            continue
        result[relative] = digest(path)
    return result


def memory_fingerprint(files: dict[str, str]) -> str:
    payload = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return digest_bytes(payload)


def refresh_memory_state() -> tuple[dict, list[str]]:
    # state/ is disposable; the ledger travels with memory.
    files = memory_file_map()
    fingerprint = memory_fingerprint(files)
    previous = load_json(MEMORY_STATE_PATH) or {}
    ledger = load_json(LEDGER_PATH) or {}
    status = load_json(STATUS_PATH) or {}
    fallback = max(
        [
            int(record.get("memory_revision", 0))
            for record in ledger.get("records", [])
            if isinstance(record, dict)
        ]
        + [int(status.get("memory_revision", 0) or 0)],
        default=0,
    )
    previous_revision = max(int(previous.get("memory_revision") or 0), fallback)
    if previous.get("memory_hash") == fingerprint and previous_revision:
        state = dict(previous)
        state["files"] = files
        state["memory_revision"] = previous_revision
        changed: list[str] = []
        if int(previous.get("memory_revision", 0) or 0) != previous_revision:
            save_json(MEMORY_STATE_PATH, state)
    else:
        previous_files = previous.get("files") or {}
        changed = sorted(
            [name for name, digest_value in files.items() if previous_files.get(name) != digest_value]
            + sorted(set(previous_files) - set(files))
        )
        revision = previous_revision + 1
        state = {
            "memory_revision": revision,
            "memory_hash": fingerprint,
            "updated_at": iso_now(),
            "files": files,
        }
        save_json(MEMORY_STATE_PATH, state)
    state["memory_revision"] = int(state["memory_revision"])
    state["memory_hash"] = str(state["memory_hash"])
    return state, changed


def state_description(code: str) -> str:
    return {
        "enabled": "团队已启用，IDE 桥接生效",
        "carried": "团队已带走，可安全移动",
        "retained_modified": "团队已带走；用户修改过的桥接已保留",
        "blocked": "操作已阻止，请先处理原项目",
        "retained": "团队未启用，可安全移动",
    }.get(code, code)


def update_status(
    state: dict,
    current_state: str,
    project: Path | None = None,
    carry_time: str | None = None,
) -> dict:
    team = load_team_data()
    old = load_json(STATUS_PATH) or {}
    recent = [str(item) for item in old.get("recent_projects", []) if item]
    project_text = str(project.resolve()) if project is not None else None
    if project_text:
        recent = [project_text] + [item for item in recent if item != project_text]
    card = {
        "schema_version": 1,
        "team_version": team["team_version"],
        "capsule_id": team.get("capsule_id"),
        "memory_version": int(state.get("memory_revision", 0)),
        "memory_revision": int(state.get("memory_revision", 0)),
        "memory_hash": state.get("memory_hash"),
        "created_at": old.get("created_at") or f"{team.get('created', '1970-01-01')}T00:00:00",
        "updated_at": iso_now(),
        "current_state": current_state,
        "state_description": state_description(current_state),
        "current_project": None if current_state in {"carried", "retained_modified"} else project_text,
        "recent_projects": recent[:10],
        "recent_carry_time": carry_time or old.get("recent_carry_time"),
    }
    if old.get("upgrade_history"):
        card["upgrade_history"] = old["upgrade_history"]
    save_json(STATUS_PATH, card)
    return card


def append_carry_record(project: Path, state: dict, changed: list[str], status: str) -> None:
    ledger = load_json(LEDGER_PATH) or {"schema_version": 1, "capsule_id": capsule_id(), "records": []}
    if not isinstance(ledger, dict) or not isinstance(ledger.get("records"), list):
        raise ValueError("记忆账本无效，请人工检查 AI-Team/memory/记忆账本.json")
    ledger["schema_version"] = 1
    ledger["capsule_id"] = capsule_id()
    ledger["records"].append(
        {
            "carried_at": iso_now(),
            "project": str(project.resolve()),
            "status": status,
            "memory_revision": int(state["memory_revision"]),
            "memory_hash": state["memory_hash"],
            "changed_files": changed,
            "source_capsule_id": capsule_id(),
        }
    )
    save_json(LEDGER_PATH, ledger)


def enable_capsule(python_path: Path, force: bool = False) -> tuple[int, dict]:
    memory_state, memory_changed = refresh_memory_state()
    capsule_rel = capsule_relative(PROJECT_ROOT)
    created_dirs: list[str] = []
    entries: list[dict] = []
    created: list[str] = []
    merged: list[str] = []
    repaired: list[str] = []
    conflicts: list[str] = []

    marker = read_project_marker()
    if marker and marker.get("capsule_rel") and marker.get("capsule_rel") != capsule_rel and not force:
        report = {
            "operation": "enable",
            "status": "blocked",
            "created": [],
            "merged": [],
            "repaired": [],
            "retained": [],
            "conflicts": [
                f"项目当前启用的是 {marker.get('capsule_rel')}，当前胶囊是 {capsule_rel}；如需切换或回退请加 --force。"
            ],
            "memory_changed": memory_changed,
        }
        save_json(LAST_REPORT_PATH, report)
        return 2, report

    old = load_json(MANIFEST_PATH)
    if old:
        old_project = Path(old.get("project_root", "")).resolve()
        if old_project != PROJECT_ROOT.resolve() and not force:
            update_status(memory_state, "blocked", old_project)
            report = {
                "operation": "enable",
                "status": "blocked",
                "created": [],
                "merged": [],
                "repaired": [],
                "retained": [],
                "conflicts": ["胶囊仍记录为在其他项目启用，请先在原项目双击带走团队（或显式 --force）"],
                "memory_changed": memory_changed,
            }
            save_json(LAST_REPORT_PATH, report)
            return 2, report

    managed_paths = {
        entry.get("path")
        for entry in (old or {}).get("entries", [])
        if entry.get("mode") == "file" and entry.get("path")
    }

    agents = PROJECT_ROOT / "AGENTS.md"
    block = agents_block(python_path, capsule_rel)
    try:
        outcome = replace_marked_block(agents, block)
    except ValueError as exc:
        report = {
            "operation": "enable",
            "status": "blocked",
            "created": created,
            "merged": merged,
            "repaired": repaired,
            "retained": [],
            "conflicts": [str(exc)],
            "memory_changed": memory_changed,
        }
        save_json(LAST_REPORT_PATH, report)
        return 2, report
    entries.append({"kind": "agents-block", "path": "AGENTS.md", "mode": "block", "block": base64.b64encode(block).decode("ascii")})
    if outcome == "created":
        created.append("AGENTS.md")
    elif outcome == "appended":
        merged.append("AGENTS.md（追加可逆标记区块）")
    elif outcome == "replaced":
        repaired.append("AGENTS.md（原地更新团队标记区块，保留项目自定义内容）")

    # Claude Code: mirror the team block only when the project already uses CLAUDE.md.
    claude_md = PROJECT_ROOT / "CLAUDE.md"
    if claude_md.exists():
        claude_cblock = claude_block(python_path, capsule_rel)
        try:
            claude_outcome = replace_marked_block(claude_md, claude_cblock)
        except ValueError as exc:
            report = {
                "operation": "enable",
                "status": "blocked",
                "created": created,
                "merged": merged,
                "repaired": repaired,
                "retained": [],
                "conflicts": [str(exc)],
                "memory_changed": memory_changed,
            }
            save_json(LAST_REPORT_PATH, report)
            return 2, report
        entries.append({"kind": "claude-block", "path": "CLAUDE.md", "mode": "block", "block": base64.b64encode(claude_cblock).decode("ascii")})
        if claude_outcome == "appended":
            merged.append("CLAUDE.md（追加可逆标记区块）")
        elif claude_outcome == "replaced":
            repaired.append("CLAUDE.md（原地更新团队标记区块）")

    for kind, relative, source_relative in BRIDGES:
        source = bridge_source(source_relative, python_path, capsule_rel)
        original_target = PROJECT_ROOT / relative
        managed = relative in managed_paths or (
            original_target.is_file() and MARKER.encode("utf-8") in original_target.read_bytes()
        )
        if original_target.exists() and not managed:
            target = choose_target(kind, original_target, source, conflicts)
            if target != original_target and kind in {"codex-agent", "antigravity-agent"}:
                if kind == "codex-agent":
                    source = source.replace(f'name = "{Path(relative).stem}"'.encode(), f'name = "{target.stem}"'.encode())
                else:
                    source = source.replace(f"name: portable-ai-team-{Path(relative).parent.name}".encode(), f"name: {target.parent.name}".encode())
        else:
            target = original_target
        add_created_parents(target, created_dirs)
        if not target.exists():
            target.write_bytes(source)
            created.append(target.relative_to(PROJECT_ROOT).as_posix())
        elif managed:
            target.write_bytes(source)
            repaired.append(target.relative_to(PROJECT_ROOT).as_posix())
        entries.append({"kind": kind, "path": target.relative_to(PROJECT_ROOT).as_posix(), "mode": "file", "digest": digest(target)})

    manifest = {
        "marker": MARKER,
        "project_root": str(PROJECT_ROOT.resolve()),
        "capsule_root": str(CAPSULE_ROOT.resolve()),
        "capsule_rel": capsule_rel,
        "capsule_anchor": capsule_anchor(),
        "enabled_at": iso_now(),
        "python_path": str(python_path),
        "entries": entries,
        "created_dirs": created_dirs,
    }
    save_json(MANIFEST_PATH, manifest)
    write_project_marker()
    status = "repaired" if old and (repaired or merged) else "enabled"
    report = {
        "operation": "enable",
        "status": status,
        "created": created,
        "merged": merged,
        "repaired": repaired,
        "retained": [],
        "conflicts": conflicts,
        "memory_changed": memory_changed,
    }
    save_json(LAST_REPORT_PATH, report)
    update_status(memory_state, "enabled", PROJECT_ROOT)
    return 0, report


def carry_capsule() -> tuple[int, dict]:
    manifest = load_json(MANIFEST_PATH)
    memory_state, memory_changed = refresh_memory_state()
    if not manifest:
        update_status(memory_state, "retained")
        report = {"operation": "carry", "status": "not_enabled", "removed": [], "retained": [], "conflicts": [], "memory_changed": memory_changed}
        save_json(LAST_REPORT_PATH, report)
        return 0, report
    enabled_project = Path(manifest.get("project_root", "")).resolve()
    if enabled_project != PROJECT_ROOT.resolve():
        update_status(memory_state, "blocked", enabled_project)
        report = {"operation": "carry", "status": "blocked", "removed": [], "retained": [], "conflicts": ["胶囊位置与启用项目不一致，请放回原项目后再带走"], "memory_changed": memory_changed}
        save_json(LAST_REPORT_PATH, report)
        return 2, report

    removed: list[str] = []
    retained: list[str] = []
    remaining: list[dict] = []
    for entry in manifest.get("entries", []):
        target = PROJECT_ROOT / entry["path"]
        if not target.exists():
            removed.append(entry["path"] + "（已不存在）")
            continue
        if entry["mode"] == "block":
            block = base64.b64decode(entry["block"])
            content = target.read_bytes()
            if content.count(block) == 1:
                target.write_bytes(content.replace(block, b"", 1))
                removed.append(entry["path"] + " 中的团队区块")
            else:
                retained.append(entry["path"] + "（团队区块已被修改）")
                remaining.append(entry)
        elif digest(target) == entry["digest"]:
            target.unlink()
            removed.append(entry["path"])
        else:
            retained.append(entry["path"] + "（文件已被修改）")
            remaining.append(entry)

    for relative in sorted(manifest.get("created_dirs", []), key=lambda value: len(Path(value).parts), reverse=True):
        directory = PROJECT_ROOT / relative
        if directory.exists() and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()

    if remaining:
        manifest["entries"] = remaining
        save_json(MANIFEST_PATH, manifest)
        status = "retained_modified"
    else:
        MANIFEST_PATH.unlink(missing_ok=True)
        status = "carried"
    marker_path = PROJECT_ROOT / PROJECT_MARKER
    if marker_path.is_file():
        marker = load_json(marker_path) or {}
        if marker.get("capsule_rel") == capsule_relative(PROJECT_ROOT):
            marker_path.unlink()
    append_carry_record(enabled_project, memory_state, memory_changed, status)
    report = {"operation": "carry", "status": status, "removed": removed, "retained": retained, "conflicts": [], "memory_changed": memory_changed}
    save_json(LAST_REPORT_PATH, report)
    update_status(memory_state, status, project=enabled_project, carry_time=iso_now())
    return 0, report


def validate_capsule() -> tuple[int, dict]:
    manifest = load_json(MANIFEST_PATH)
    errors: list[str] = []
    if not manifest:
        errors.append("团队尚未启用")
    else:
        for entry in manifest.get("entries", []):
            target = PROJECT_ROOT / entry["path"]
            if not target.exists():
                errors.append(f"桥接缺失: {entry['path']}")
            elif entry["mode"] == "file" and digest(target) != entry["digest"]:
                errors.append(f"桥接已修改: {entry['path']}")
            elif entry["mode"] == "block" and base64.b64decode(entry["block"]) not in target.read_bytes():
                errors.append("AGENTS.md 团队区块已修改")
    return (1 if errors else 0), {"operation": "validate", "status": "failed" if errors else "valid", "errors": errors}


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:3]):
        raise ValueError("团队版本无效")
    padded = parts + ["0"] * (3 - len(parts))
    return tuple(int(part) for part in padded[:3])


def load_other_identity(other_value: str) -> tuple[Path, dict]:
    other = Path(other_value).expanduser().resolve()
    if not other.is_dir():
        raise ValueError(f"待合并胶囊不存在或不是文件夹: {other}")
    team_path = other / "AI-Team" / "team.json"
    capsule_tool = other / "AI-Team" / "capsule.py"
    if not team_path.is_file() or not capsule_tool.is_file():
        raise ValueError("待合并对象不是 Portable AI Team 胶囊")
    try:
        data = load_json(team_path) or {}
    except json.JSONDecodeError as exc:
        raise ValueError("待合并胶囊 team.json 无法解析") from exc
    version = data.get("team_version")
    if not isinstance(version, str):
        raise ValueError("待合并胶囊缺少 team_version")
    other_version = version_tuple(version)
    if other_version < MINIMUM_MERGE_VERSION:
        raise ValueError(f"团队版本不兼容: {version}（当前支持 v2.3+）")
    return other, data


def safe_memory_files(memory_dir: Path) -> list[tuple[Path, str]]:
    if not memory_dir.exists():
        return []
    root = memory_dir.resolve()
    result: list[tuple[Path, str]] = []
    for path in sorted(p for p in memory_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".md"):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"记忆目录包含不安全链接: {path}")
        relative = path.relative_to(memory_dir).as_posix()
        if relative == "merge-inbox" or relative.startswith("merge-inbox/"):
            continue
        result.append((path, relative))
    return result


def conflict_already_staged(relative: str, content: bytes) -> bool:
    inbox = MEMORY_DIR / "merge-inbox"
    if not inbox.exists():
        return False
    for candidate in inbox.rglob("*"):
        if not candidate.is_file() or not candidate.name.endswith(Path(relative).name):
            continue
        if candidate.is_file() and candidate.read_bytes() == content:
            return True
    return False


def safe_target_path(relative: str) -> Path:
    target = MEMORY_DIR / relative
    resolved = target.resolve()
    if not resolved.is_relative_to(MEMORY_DIR.resolve()) or target.is_symlink():
        raise ValueError(f"合并目标越界: {relative}")
    return target


def write_merge_review(operations: list[dict], other_id: str) -> Path:
    review_dir = MEMORY_DIR / "merge-inbox"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / "merge-review.md"
    lines = [
        "# 团队记忆合并审查",
        "",
        f"- 合并来源胶囊 ID：{other_id}",
        f"- 生成时间：{iso_now()}",
        "",
        "同名记忆内容不同，当前文件未被覆盖。请逐项选择保留或合并内容。",
        "",
        "| 记忆文件 | 当前文件 | 来源文件 |",
        "| --- | --- | --- |",
    ]
    for operation in operations:
        lines.append(f"| `{operation['relative']}` | `{operation['destination']}` | `{operation['source']}` |")
    lines.extend(["", "处理完成后，可将选定内容写回对应记忆文件；来源文件保留在 merge-inbox 中。", ""])
    review_path.write_text("\n".join(lines), encoding="utf-8")
    return review_path


def merge_capsule(other_value: str) -> tuple[int, dict]:
    other, other_team = load_other_identity(other_value)
    self_id = capsule_id()
    if other.resolve() == CAPSULE_ROOT.resolve():
        raise ValueError("不能自我合并同一胶囊；请使用另一份独立的 Portable AI Team")
    other_id = str(other_team.get("capsule_id") or f"legacy-{other.name}")
    if MANIFEST_PATH.exists():
        raise ValueError("当前胶囊仍处于启用状态，请先双击带走后再合并")
    if (other / "state" / "installation.json").exists():
        raise ValueError("来源胶囊仍处于启用状态，请先在原项目带走后再合并")

    other_memory = other / "AI-Team" / "memory"
    other_ledger = other / "AI-Team" / "memory" / "记忆账本.json"
    source_files = safe_memory_files(other_memory)
    other_ledger_data = load_json(other_ledger) or {"schema_version": 1, "records": []}
    if not isinstance(other_ledger_data, dict) or not isinstance(other_ledger_data.get("records"), list):
        raise ValueError("来源记忆账本无效")
    if other_ledger_data.get("schema_version", 1) != 1:
        raise ValueError("来源记忆账本 schema 不兼容")

    copied: list[str] = []
    conflicts: list[str] = []
    unchanged: list[str] = []
    operations: list[dict] = []
    for source, relative in source_files:
        target = safe_target_path(relative)
        content = source.read_bytes()
        if target.exists():
            if digest_bytes(content) == digest(target):
                unchanged.append(relative)
                continue
            if conflict_already_staged(relative, content):
                unchanged.append(relative + "（冲突已在 merge-inbox）")
                continue
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            inbox_target = MEMORY_DIR / "merge-inbox" / f"{timestamp}-{relative}"
            operations.append({
                "relative": relative,
                "destination": target,
                "source": source,
                "inbox": inbox_target,
            })
            conflicts.append(relative)
        else:
            copied.append(relative)

    current_ledger = load_json(LEDGER_PATH) or {"schema_version": 1, "capsule_id": self_id, "records": []}
    if not isinstance(current_ledger, dict) or not isinstance(current_ledger.get("records"), list):
        raise ValueError("当前记忆账本无效")
    known_records = {
        json.dumps(record, ensure_ascii=False, sort_keys=True)
        for record in current_ledger["records"]
        if isinstance(record, dict)
    }
    ledger_imported: list[str] = []
    for record in other_ledger_data["records"]:
        if not isinstance(record, dict):
            continue
        normalized = dict(record)
        normalized.setdefault("source_capsule_id", other_id)
        serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        if serialized not in known_records:
            known_records.add(serialized)
            current_ledger["records"].append(normalized)
            ledger_imported.append(str(normalized.get("carried_at") or "未记录时间"))

    changed_names = copied + conflicts
    if not changed_names and not ledger_imported:
        report = {
            "operation": "merge",
            "status": "already_merged",
            "source_capsule_id": other_id,
            "copied": [],
            "unchanged": unchanged,
            "conflicts": [],
            "ledger_imported": [],
            "backup": None,
            "review": None,
        }
        return 0, report

    backup_dir = CAPSULE_ROOT / "AI-Team" / "merge-backups" / datetime.now().strftime("merge-%Y%m%d-%H%M%S-%f")
    backup_dir.mkdir(parents=True, exist_ok=True)
    if MEMORY_DIR.exists():
        shutil.copytree(
            MEMORY_DIR,
            backup_dir / "memory",
            ignore=shutil.ignore_patterns("__pycache__"),
            symlinks=False,
        )
    (backup_dir / "backup.json").write_text(
        json.dumps({"created_at": iso_now(), "source_capsule_id": other_id}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for operation in operations:
        operation["inbox"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(operation["source"], operation["inbox"])
    for relative in copied:
        target = safe_target_path(relative)
        source = other_memory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    current_ledger["schema_version"] = 1
    current_ledger["capsule_id"] = self_id
    current_ledger["last_merged_at"] = iso_now()
    current_ledger["last_merged_from"] = other_id
    save_json(LEDGER_PATH, current_ledger)

    review_path = write_merge_review(operations, other_id) if operations else None
    memory_state, _ = refresh_memory_state()
    old_status = (load_json(STATUS_PATH) or {}).get("current_state")
    merged_status = old_status if old_status in {"carried", "retained_modified", "retained"} else "retained"
    update_status(memory_state, merged_status)
    report_path = CAPSULE_ROOT / "AI-Team" / "merge-reports" / f"merge-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
    report = {
        "operation": "merge",
        "status": "merged_with_review" if conflicts else "merged",
        "source_capsule_id": other_id,
        "copied": copied,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "ledger_imported": ledger_imported,
        "backup": str(backup_dir),
        "review": str(review_path) if review_path else None,
        "memory_revision": memory_state["memory_revision"],
    }
    save_json(report_path, report)
    return 0, report


def print_report(report: dict) -> None:
    titles = {
        "copied": "已复制记忆",
        "unchanged": "内容一致",
        "ledger_imported": "已导入账本记录",
        "removed": "已移除",
        "retained": "已保留",
        "conflicts": "冲突/提示",
        "errors": "问题",
    }
    status_text = {
        "enabled": "团队启用成功",
        "already_enabled": "团队已经启用",
        "carried": "团队桥接已安全移除，可以带走 Portable-AI-Team 文件夹",
        "retained_modified": "带走操作完成，用户修改过的桥接已保留",
        "not_enabled": "未发现启用清单，无需移除",
        "valid": "团队桥接校验通过",
        "failed": "团队桥接校验失败",
        "blocked": "操作已阻止",
        "merged": "记忆合并完成",
        "merged_with_review": "记忆合并完成；同名不同内容已进入 merge-inbox，未覆盖当前文件",
        "already_merged": "两份团队记忆已完成合并或内容一致",
    }
    print(status_text.get(report.get("status"), report.get("status", "完成")))
    for key, title in titles.items():
        values = report.get(key) or []
        if values:
            print(f"{title}:")
            for value in values:
                print(f"- {value}")
    for check in report.get("checks", []):
        mark = "✓" if check.get("ok") else "✗"
        line = f"{mark} {check.get('name')}"
        if check.get("detail"):
            line += f" — {check['detail']}"
        print(line)
    if report.get("backup"):
        print(f"备份位置: {report['backup']}")
    if report.get("review"):
        print(f"审查文件: {report['review']}")
    if report.get("memory_changed"):
        print("本次记忆变化:")
        for value in report["memory_changed"]:
            print(f"- {value}")


def validate_llm_config(cfg: object) -> list[str]:
    """Offline structural check of LLM config (no network). Never leaks secrets."""
    if not isinstance(cfg, dict):
        return ["LLM配置必须是 JSON 对象"]
    errors: list[str] = []
    if not isinstance(cfg.get("enabled"), bool):
        errors.append("enabled 必须是布尔值")
    models = cfg.get("models")
    if not isinstance(models, dict) or not models:
        errors.append("models 必须是非空对象")
    routing = cfg.get("routing", {})
    if isinstance(routing, dict):
        for name, role in routing.items():
            if not isinstance(role, str) or (models and role not in models):
                errors.append(f"routing[{name}] 指向未定义角色")
                break
    if cfg.get("enabled"):
        base_url = cfg.get("base_url")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            errors.append("base_url 必须以 http(s):// 开头")
        if not isinstance(cfg.get("api_key"), str) or not cfg.get("api_key", "").strip():
            errors.append("api_key 必须是非空字符串")
    return errors


def probe_one(cfg: dict, model_id: str) -> tuple[bool, str]:
    import urllib.request
    url = str(cfg.get("base_url", "")).rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": "回复OK"}],
        "max_tokens": 5,
    }).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.get('api_key', '')}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            json.loads(response.read().decode("utf-8"))
            return True, "响应正常"
    except Exception as exc:  # noqa: BLE001 - report, never crash doctor
        return False, str(exc)[:160]


def doctor_capsule() -> tuple[int, dict]:
    """Health check: project root, versions, bridges, memory, model routing."""
    global PROJECT_ROOT
    team = load_team_data()
    manifest = load_json(MANIFEST_PATH)
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        resolved = resolve_project_root()
        details = str(resolved)
        if manifest and Path(manifest.get("project_root", "")).resolve() != resolved.resolve():
            add("项目根", False, f"解析为 {resolved}，与安装清单 {manifest.get('project_root')} 不一致")
        else:
            add("项目根", True, details)
    except ValueError as exc:
        add("项目根", False, str(exc))
        if manifest:
            PROJECT_ROOT = Path(manifest.get("project_root", CAPSULE_ROOT.parent)).resolve()

    if manifest:
        expected_capsule = (PROJECT_ROOT / capsule_anchor()).resolve()
        add(
            "稳定路径",
            CAPSULE_ROOT.resolve() == expected_capsule,
            f"期望={expected_capsule} / 实际={CAPSULE_ROOT.resolve()}",
        )

    try:
        add("Python 路径", True, str(configured_python_path()))
    except ValueError as exc:
        add("Python 路径", False, str(exc))

    team_version = str(team.get("team_version", ""))
    add("团队版本", bool(team_version), f"v{team_version} / 记忆谱系 {team.get('capsule_id')}")

    release = load_json(VERSION_PATH)
    if not release:
        add("VERSION 一致", False, "缺少根目录 VERSION.json")
    else:
        release_version = str(release.get("team_version", ""))
        release_lineage = str(release.get("capsule_id", ""))
        version_ok = (
            release_version == team_version
            and release_lineage == str(team.get("capsule_id", ""))
        )
        add(
            "VERSION 一致",
            version_ok,
            f"team.json={team_version}/{team.get('capsule_id')} / "
            f"VERSION.json={release_version or '缺失'}/{release_lineage or '缺失'}",
        )
        for alias in sorted(CAPSULE_ROOT.glob("VERSION_V*.json")):
            alias_data = load_json(alias) or {}
            alias_version = str(alias_data.get("team_version", ""))
            alias_lineage = str(alias_data.get("capsule_id", ""))
            add(
                f"版本副本 {alias.name}",
                alias_version == team_version and alias_lineage == str(team.get("capsule_id", "")),
                f"{alias_version or '缺失'}/{alias_lineage or '缺失'}",
            )

    history_root = CAPSULE_ROOT / "AI-Team" / "history"
    history_manifest_path = history_root / "manifest.json"
    history_workspaces_root = (history_root / "workspaces").resolve()
    history_problems: list[str] = []
    if not (history_root / "README.md").is_file():
        history_problems.append("缺少历史区说明 README.md")
    history_manifest = load_json(history_manifest_path)
    if not isinstance(history_manifest, dict):
        history_problems.append("缺少有效 manifest.json")
        history_entries: list[dict] = []
    else:
        history_entries = [
            entry for entry in history_manifest.get("workspaces", [])
            if isinstance(entry, dict)
        ]
        for entry in history_entries:
            snapshot = str(entry.get("snapshot", "")).replace("/", os.sep)
            if not snapshot:
                history_problems.append("manifest 中存在空快照路径")
                continue
            candidate = (CAPSULE_ROOT / snapshot).resolve()
            if history_workspaces_root != candidate and history_workspaces_root not in candidate.parents:
                history_problems.append(f"快照越界: {entry.get('snapshot')}")
            elif not candidate.is_dir():
                history_problems.append(f"快照缺失: {entry.get('snapshot')}")
    if len(history_problems) > 5:
        history_detail = "；".join(history_problems[:5]) + f"；另有 {len(history_problems) - 5} 项"
    else:
        history_detail = "；".join(history_problems)
    add(
        "团队历史",
        not history_problems,
        history_detail or f"{len(history_entries)} 个完整工作区快照",
    )

    state = load_json(STATUS_PATH) or {}
    if state:
        state_version = str(state.get("team_version", ""))
        add("版本一致", state_version == team_version, f"team.json={team_version} / 团队状态.json={state_version or '缺失'}")
    else:
        add("版本一致", True, "母版无 团队状态.json（项目胶囊会持有）")

    cfg_path = CAPSULE_ROOT / "LLM配置.json"
    cfg = None
    if not cfg_path.exists():
        add("LLM 配置", True, "未配置外部 LLM，使用宿主内置子代理（可选）")
    else:
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            add("LLM 配置", False, f"JSON 解析失败: {exc}")
            cfg = None
    if cfg is not None:
        errors = validate_llm_config(cfg)
        if errors:
            add("LLM 配置", False, "；".join(errors))
        elif not cfg.get("enabled"):
            add("LLM 配置", True, "格式正确，但 enabled=false（将回退宿主模型）")
        else:
            add("LLM 配置", True, "格式正确且已启用")
            for model_id in dict.fromkeys(cfg.get("models", {}).values()):
                ok, detail = probe_one(cfg, model_id)
                add(f"模型连通 {model_id}", ok, detail)

    tiers_path = CAPSULE_ROOT / "AI-Team" / "config" / "model-tiers.json"
    if not tiers_path.is_file():
        add("模型路由", False, "缺少 AI-Team/config/model-tiers.json")
    else:
        try:
            tiers = json.loads(tiers_path.read_text(encoding="utf-8"))
            required = {"fast", "standard", "high-risk", "vision"}
            missing = sorted(required - set(tiers.get("tiers", {})))
            add("模型路由", not missing, "档位齐全" if not missing else f"缺少档位: {', '.join(missing)}")
        except (json.JSONDecodeError, OSError) as exc:
            add("模型路由", False, f"JSON 解析失败: {exc}")

    vcode, vreport = validate_capsule()
    if not manifest:
        add("桥接", False, "团队尚未启用（双击启用团队 或 python AI-Team/capsule.py enable）")
    else:
        add("桥接", vcode == 0, "；".join(vreport.get("errors", [])) or "校验通过")
        path_problems: list[str] = []
        anchor = capsule_anchor()
        for entry in manifest.get("entries", []):
            target = PROJECT_ROOT / entry.get("path", "")
            if not target.is_file():
                continue
            text = target.read_text(encoding="utf-8", errors="ignore")
            if f"{anchor}/{anchor}" in text:
                path_problems.append(f"{entry['path']}: 重复锚点")
            if entry.get("mode") == "file":
                stale_versions = sorted(set(re.findall(r"Portable-AI-TeamV[0-9][0-9A-Za-z._-]*", text)))
                for stale_version in stale_versions:
                    path_problems.append(
                        f"{entry['path']}: 不允许版本化运行时路径 {stale_version}"
                    )
            for match in re.findall(r"`([^`]*AI-Team/[^`]*)`", text):
                if not match.startswith(("Portable-AI-Team", "{{")):
                    continue
                if (PROJECT_ROOT / match.replace("/", os.sep)).exists():
                    continue
                path_problems.append(f"{entry['path']}: {match} 不存在")
        add("桥接路径", not path_problems, "；".join(path_problems[:5]) or "全部可解析")

    memory_problems: list[str] = []
    for path in sorted((CAPSULE_ROOT / "AI-Team" / "memory").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        entries = sum(1 for line in text.splitlines() if line.startswith("## "))
        if entries > 40 or len(text) > 8000:
            memory_problems.append(f"{path.name}: {entries}条/{len(text)}字符")
    add("记忆容量", True, "；".join(memory_problems) or "未超限")

    failed = [c for c in checks if not c["ok"]]
    report = {"operation": "doctor", "status": "healthy" if not failed else "attention", "checks": checks}
    return (0 if not failed else 1), report


def main() -> int:
    parser = argparse.ArgumentParser(description="Portable AI Team 团队胶囊")
    parser.add_argument("command", choices=("enable", "carry", "validate", "status", "merge", "doctor"))
    parser.add_argument("--python", dest="python_path", help="本项目默认 Python 解释器绝对路径")
    parser.add_argument("--other", dest="other", help="待合并的另一个 Portable AI Team 文件夹路径")
    parser.add_argument("--project", dest="project", help="业务项目根目录（嵌套部署时必填，或拖拽项目文件夹到启用脚本）")
    parser.add_argument("--force", action="store_true", help="允许切换或回退到不同版本的胶囊")
    args = parser.parse_args()
    try:
        set_project_root(args.project)
    except ValueError as exc:
        if args.command in {"enable", "carry", "merge"}:
            report = {"operation": args.command, "status": "blocked", "conflicts": [str(exc)]}
            print_report(report)
            return 2
        PROJECT_ROOT = CAPSULE_ROOT.parent
    if args.command == "enable":
        try:
            python_path = configured_python_path(args.python_path)
        except ValueError as exc:
            report = {"operation": "enable", "status": "blocked", "created": [], "merged": [], "retained": [], "conflicts": [str(exc)]}
            print_report(report)
            return 2
        code, report = enable_capsule(python_path, force=args.force)
    elif args.command == "carry":
        code, report = carry_capsule()
    elif args.command == "validate":
        code, report = validate_capsule()
    elif args.command == "doctor":
        code, report = doctor_capsule()
    elif args.command == "merge":
        if not args.other:
            report = {"operation": "merge", "status": "blocked", "conflicts": ["请把另一个 Portable-AI-Team 文件夹拖到双击合并团队.cmd 上"]}
            print_report(report)
            return 2
        try:
            code, report = merge_capsule(args.other)
        except (ValueError, OSError) as exc:
            report = {"operation": "merge", "status": "blocked", "conflicts": [str(exc)]}
            print_report(report)
            return 2
    else:
        report = load_json(LAST_REPORT_PATH) or {"status": "not_enabled"}
        code = 0
    print_report(report)
    return code


if __name__ == "__main__":
    configure_utf8_io()
    raise SystemExit(main())
    # state/ is disposable; the ledger travels with memory.
