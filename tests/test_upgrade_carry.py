import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE_NAME = "Portable-AI-Team"


def write_release_files(capsule: Path, version: str, capsule_id: str) -> None:
    major_minor = ".".join(version.split(".")[:2])
    payload = {
        "schema": 1,
        "team_version": version,
        "capsule_id": capsule_id,
        "released_at": "2026-11-06",
        "path_contract": STABLE_NAME,
        "notes": f"AI-Team/versions/V{major_minor}.md",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    (capsule / "VERSION.json").write_text(text, encoding="utf-8")
    (capsule / f"VERSION_V{major_minor}.json").write_text(text, encoding="utf-8")


def copy_capsule(destination: Path, version: str | None = None) -> Path:
    ignore = shutil.ignore_patterns("__pycache__", "state", ".pytest_cache", "history")
    shutil.copytree(ROOT / "AI-Team", destination / "AI-Team", ignore=ignore)
    history_source = ROOT / "AI-Team" / "history"
    if history_source.is_dir():
        history_destination = destination / "AI-Team" / "history"
        history_destination.mkdir(parents=True)
        shutil.copy2(history_source / "README.md", history_destination / "README.md")
        (history_destination / "manifest.json").write_text(
            json.dumps({"schema": 1, "updated_at": None, "workspaces": []}, indent=2) + "\n",
            encoding="utf-8",
        )
    (destination / "Python路径.txt").write_text(str(Path(sys.executable).resolve()), encoding="utf-8")
    (destination / "胶囊根.txt").write_text(f"{STABLE_NAME}\n", encoding="utf-8")

    team_path = destination / "AI-Team" / "team.json"
    team = json.loads(team_path.read_text(encoding="utf-8"))
    if version is not None:
        team["team_version"] = version
        team_path.write_text(json.dumps(team, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        team_py = destination / "AI-Team" / "team.py"
        team_py.write_text(
            team_py.read_text(encoding="utf-8").replace(
                f'TEAM_VERSION = "{json.loads((ROOT / "AI-Team" / "team.json").read_text(encoding="utf-8"))["team_version"]}"',
                f'TEAM_VERSION = "{version}"',
            ),
            encoding="utf-8",
        )
    write_release_files(destination, team["team_version"], team["capsule_id"])
    return destination


def run_capsule(capsule: Path, command: str, *extra: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return subprocess.run(
        [sys.executable, str(capsule / "AI-Team" / "capsule.py"), command, *extra],
        cwd=capsule,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )


def run_upgrade(
    source: Path,
    project: Path,
    new_version: str,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(source / "AI-Team" / "upgrade_carry.ps1"),
            "-NewVersion", new_version,
            "-NewCapsulePath", str(source),
            "-ProjectRoot", str(project),
            *extra,
        ],
        cwd=project,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


class StablePathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.project = Path(self.tmp.name) / "项目"
        self.project.mkdir()
        (self.project / ".git").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_stable_layout_enable_renders_real_path_and_doctor_passes(self):
        capsule = copy_capsule(self.project / STABLE_NAME)
        history_manifest = json.loads(
            (capsule / "AI-Team" / "history" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(history_manifest["workspaces"], [])
        agents = self.project / "AGENTS.md"
        agents.write_text(
            "# 项目自定义规则\n\n这一段必须在升级后保留。\n\n"
            "<!-- portable-ai-team-capsule:start -->\n旧区块\n<!-- portable-ai-team-capsule:end -->\n\n"
            "尾部自定义内容。\n",
            encoding="utf-8",
        )

        result = run_capsule(capsule, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        content = agents.read_text(encoding="utf-8")
        self.assertIn("这一段必须在升级后保留", content)
        self.assertIn("尾部自定义内容", content)
        self.assertIn("Portable-AI-Team/AI-Team/agents/AgentA.md", content)
        self.assertNotIn("Portable-AI-TeamV", content)
        self.assertEqual(content.count("<!-- portable-ai-team-capsule:start -->"), 1)

        bridge = (self.project / ".codex" / "agents" / "agent-b.toml").read_text(encoding="utf-8")
        self.assertIn("Portable-AI-Team/AI-Team/agents/AgentB.md", bridge)
        self.assertNotIn("{{CAPSULE_PATH}}", bridge)
        self.assertNotIn("Portable-AI-TeamV", bridge)

        marker = json.loads((self.project / ".portable-ai-team.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["capsule_rel"], STABLE_NAME)
        self.assertEqual(marker["capsule_version"], "4.2.0")

        doctor = run_capsule(capsule, "doctor", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

        again = run_capsule(capsule, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        final = agents.read_text(encoding="utf-8")
        self.assertEqual(final.count("这一段必须在升级后保留"), 1)
        self.assertEqual(final.count("<!-- portable-ai-team-capsule:start -->"), 1)

    def test_enable_blocks_switch_without_force(self):
        old = copy_capsule(
            self.project / "Portable-AI-TeamV3.0" / "dist" / STABLE_NAME,
            "3.1.1",
        )
        new = copy_capsule(self.project / STABLE_NAME)
        (self.project / "AGENTS.md").write_text("# 项目\n", encoding="utf-8")

        first = run_capsule(old, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        blocked = run_capsule(new, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)

        forced = run_capsule(new, "enable", "--project", str(self.project), "--python", sys.executable, "--force")
        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        bridge = (self.project / ".codex" / "agents" / "agent-b.toml").read_text(encoding="utf-8")
        self.assertIn("Portable-AI-Team/AI-Team", bridge)
        self.assertNotIn("Portable-AI-TeamV", bridge)

    def test_enable_preserves_upgrade_history(self):
        capsule = copy_capsule(self.project / STABLE_NAME)
        (self.project / "AGENTS.md").write_text("# 项目\n", encoding="utf-8")

        first = run_capsule(capsule, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        status_path = capsule / "团队状态.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        history = [{"from_version": "4.0.0", "to_version": "4.1.0", "status": "ok"}]
        status["upgrade_history"] = history
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        again = run_capsule(capsule, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(json.loads(status_path.read_text(encoding="utf-8"))["upgrade_history"], history)

    def test_doctor_rejects_versioned_runtime_path(self):
        capsule = copy_capsule(self.project / STABLE_NAME)
        (self.project / "AGENTS.md").write_text("# 项目\n", encoding="utf-8")
        enabled = run_capsule(capsule, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)

        bridge = self.project / ".codex" / "agents" / "agent-b.toml"
        content = bridge.read_text(encoding="utf-8")
        bridge.write_text(
            content.replace(
                "Portable-AI-Team/AI-Team",
                "Portable-AI-TeamV3.0/dist/Portable-AI-Team/AI-Team",
            ),
            encoding="utf-8",
        )
        doctor = run_capsule(capsule, "doctor", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(doctor.returncode, 1, doctor.stdout + doctor.stderr)
        self.assertIn("不允许版本化运行时路径", doctor.stdout)

    def test_doctor_rejects_version_file_mismatch(self):
        capsule = copy_capsule(self.project / STABLE_NAME)
        (self.project / "AGENTS.md").write_text("# 项目\n", encoding="utf-8")
        enabled = run_capsule(capsule, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)

        version_path = capsule / "VERSION.json"
        version = json.loads(version_path.read_text(encoding="utf-8"))
        version["team_version"] = "9.9.9"
        version_path.write_text(json.dumps(version, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        doctor = run_capsule(capsule, "doctor", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(doctor.returncode, 1, doctor.stdout + doctor.stderr)
        self.assertIn("VERSION 一致", doctor.stdout)

    def test_upgrade_script_dry_run_targets_stable_path(self):
        old = copy_capsule(
            self.project / "Portable-AI-TeamV3.0" / "dist" / STABLE_NAME,
            "3.1.1",
        )
        new = copy_capsule(Path(self.tmp.name) / "external-master")
        (self.project / "AGENTS.md").write_text("# 项目\n", encoding="utf-8")
        enabled = run_capsule(old, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)

        result = run_upgrade(new, self.project, "V4.2", "-DryRun")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn(str(self.project / STABLE_NAME), result.stdout)
        self.assertNotIn("目标: " + str(self.project / "Portable-AI-TeamV4.1"), result.stdout)

    def test_upgrade_archives_current_keeps_v30_and_carries_private_state(self):
        legacy_v3 = copy_capsule(
            self.project / "Portable-AI-TeamV3.0" / "dist" / STABLE_NAME,
            "3.1.1",
        )
        current_v4 = copy_capsule(
            self.project / "Portable-AI-TeamV4.0" / "dist" / STABLE_NAME,
            "4.0.0",
        )
        (self.project / "AGENTS.md").write_text(
            "# 项目自定义\n\n<!-- portable-ai-team-capsule:start -->\n旧区块\n"
            "<!-- portable-ai-team-capsule:end -->\n\n尾部必须保留。\n",
            encoding="utf-8",
        )
        enabled = run_capsule(current_v4, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)

        status_path = current_v4 / "团队状态.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["recent_projects"].append("<本地路径>")
        status["upgrade_history"] = [
            {"from_version": "3.1.1", "to_version": "4.0.0", "status": "ok"}
        ]
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        local_llm = {
            "enabled": False,
            "models": {"local": "sentinel-model"},
            "routing": {},
            "max_parallel": 2,
            "fallback": "codex_builtin",
            "timeout_seconds": 30,
            "sentinel": "local-config",
        }
        (current_v4 / "LLM配置.json").write_text(
            json.dumps(local_llm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (current_v4 / "AI-Team" / "memory" / "credentials.md").write_text(
            "# sentinel credentials\n", encoding="utf-8"
        )
        (current_v4 / "AI-Team" / "memory" / "记忆账本.json").write_text(
            '{"sentinel": "local-ledger"}\n', encoding="utf-8"
        )

        external_master = copy_capsule(Path(self.tmp.name) / "external-master")
        (external_master / "AI-Team" / "memory" / "credentials.md").write_text(
            "# master credentials must not replace local\n", encoding="utf-8"
        )
        master_llm = dict(local_llm)
        master_llm["sentinel"] = "master-config"
        (external_master / "LLM配置.json").write_text(
            json.dumps(master_llm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        result = run_upgrade(external_master, self.project, "V4.2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        target = self.project / STABLE_NAME
        self.assertTrue(target.is_dir())
        self.assertTrue((target / "VERSION.json").is_file())
        self.assertTrue((target / "VERSION_V4.2.json").is_file())
        self.assertFalse((self.project / "Portable-AI-TeamV4.0").exists())
        self.assertTrue(legacy_v3.is_dir())
        self.assertTrue(list(self.project.glob(".archive-Portable-AI-TeamV4.0-*")))

        marker = json.loads((self.project / ".portable-ai-team.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["capsule_rel"], STABLE_NAME)
        self.assertEqual(marker["capsule_version"], "4.2.0")

        version = json.loads((target / "VERSION.json").read_text(encoding="utf-8"))
        team = json.loads((target / "AI-Team" / "team.json").read_text(encoding="utf-8"))
        self.assertEqual(version["team_version"], "4.2.0")
        self.assertEqual(team["team_version"], "4.2.0")

        carried = json.loads((target / "团队状态.json").read_text(encoding="utf-8"))
        self.assertIn("<本地路径>", carried["recent_projects"])
        self.assertEqual(carried["upgrade_history"][0]["to_version"], "4.0.0")
        self.assertEqual(carried["upgrade_history"][-1]["from_version"], "4.0.0")
        self.assertEqual(carried["upgrade_history"][-1]["to_dir"], STABLE_NAME)
        self.assertIn("local-config", (target / "LLM配置.json").read_text(encoding="utf-8"))
        self.assertIn(
            "sentinel credentials",
            (target / "AI-Team" / "memory" / "credentials.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "local-ledger",
            (target / "AI-Team" / "memory" / "记忆账本.json").read_text(encoding="utf-8"),
        )

        agent_b = (self.project / ".agents" / "agents" / "agent-b" / "agent.md").read_text(encoding="utf-8")
        self.assertIn("Portable-AI-Team/AI-Team", agent_b)
        self.assertNotIn("Portable-AI-TeamV4.0", agent_b)
        agents = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("尾部必须保留", agents)
        self.assertIn("Portable-AI-Team/AI-Team/agents/AgentA.md", agents)
        self.assertNotIn("Portable-AI-TeamV4.0", agents)

        doctor = run_capsule(target, "doctor", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_upgrade_carries_complete_legacy_workspace_history(self):
        legacy_root = self.project / "Portable-AI-TeamV3.0"
        legacy_capsule = copy_capsule(
            legacy_root / "dist" / STABLE_NAME,
            "3.1.1",
        )
        legacy_task = legacy_root / "AI-Team" / "tasks" / "2026-10-28-project-history.md"
        legacy_task.parent.mkdir(parents=True)
        legacy_task.write_text("# 示例项目 historical work order\n", encoding="utf-8")
        legacy_dist = legacy_root / "dist" / "old-build.txt"
        legacy_dist.write_text("legacy-dist\n", encoding="utf-8")
        legacy_git = legacy_root / ".git" / "HEAD"
        legacy_git.parent.mkdir(parents=True)
        legacy_git.write_text("ref: refs/heads/main\n", encoding="utf-8")
        legacy_cache = legacy_root / ".pytest_cache" / "v" / "cache" / "nodeids"
        legacy_cache.parent.mkdir(parents=True)
        legacy_cache.write_text("[]\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("# 项目\n", encoding="utf-8")
        enabled = run_capsule(legacy_capsule, "enable", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)

        external_master = copy_capsule(Path(self.tmp.name) / "external-master")
        result = run_upgrade(external_master, self.project, "V4.2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        target = self.project / STABLE_NAME
        snapshot = target / "AI-Team" / "history" / "workspaces" / "Portable-AI-TeamV3.0"
        self.assertTrue((snapshot / "AI-Team" / "tasks" / legacy_task.name).is_file())
        self.assertTrue((snapshot / "dist" / "old-build.txt").is_file())
        self.assertTrue((snapshot / ".git" / "HEAD").is_file())
        self.assertTrue((snapshot / ".pytest_cache" / "v" / "cache" / "nodeids").is_file())

        manifest = json.loads(
            (target / "AI-Team" / "history" / "manifest.json").read_text(encoding="utf-8")
        )
        entries = {entry["snapshot"]: entry for entry in manifest["workspaces"]}
        v3_snapshots = [
            entry for entry in manifest["workspaces"]
            if "Portable-AI-TeamV3.0" in entry["snapshot"]
        ]
        self.assertEqual(len(v3_snapshots), 1, v3_snapshots)
        legacy_entry = entries["AI-Team/history/workspaces/Portable-AI-TeamV3.0"]
        self.assertEqual(legacy_entry["version"], "3.1.1")
        self.assertGreaterEqual(legacy_entry["files"], 5)

        doctor = run_capsule(target, "doctor", "--project", str(self.project), "--python", sys.executable)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertIn("团队历史", doctor.stdout)


if __name__ == "__main__":
    unittest.main()
