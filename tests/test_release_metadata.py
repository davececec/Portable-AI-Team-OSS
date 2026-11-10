import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_unique_json(path: Path) -> dict:
    def object_pairs_hook(pairs):
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            raise ValueError(f"重复 JSON 键: {', '.join(duplicates)}")
        return dict(pairs)

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs_hook)


class ReleaseMetadataTests(unittest.TestCase):
    def test_version_is_unified(self):
        team = json.loads((ROOT / "AI-Team" / "team.json").read_text(encoding="utf-8"))
        release = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))
        aliases = sorted(ROOT.glob("VERSION_V*.json"))
        self.assertEqual(len(aliases), 1, [path.name for path in aliases])
        display_release = json.loads(aliases[0].read_text(encoding="utf-8"))
        status_path = ROOT / "团队状态.json"
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else None
        team_py = (ROOT / "AI-Team" / "team.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        start = (ROOT / "START-HERE.md").read_text(encoding="utf-8")
        version = team["team_version"]
        self.assertEqual(release["team_version"], version)
        self.assertEqual(display_release["team_version"], version)
        self.assertEqual(release["capsule_id"], team["capsule_id"])
        self.assertEqual(display_release["capsule_id"], team["capsule_id"])
        self.assertEqual(release["path_contract"], "Portable-AI-Team")
        if status is not None:
            self.assertEqual(status["team_version"], version)
        self.assertIn(f'TEAM_VERSION = "{version}"', team_py)
        self.assertIn(f"v{version}", readme)
        self.assertIn(f"v{version}", start)

    def test_upgrade_script_uses_stable_path_contract(self):
        script = (ROOT / "AI-Team" / "upgrade_carry.ps1").read_text(encoding="utf-8")
        self.assertIn("$StableName = 'Portable-AI-Team'", script)
        self.assertIn("$TargetCapsule = Join-Path $ProjectRoot $StableName", script)
        self.assertIn("VERSION.json", script)
        self.assertIn("VERSION_V*.json", script)
        self.assertIn("$HistoryWorkspacesRel", script)
        self.assertIn("Add-WorkspaceSnapshot", script)
        self.assertNotIn('$NewDirName = "Portable-AI-Team$NewVersion"', script)

    def test_distribution_keeps_version_files_and_excludes_private_state(self):
        script = (ROOT / "AI-Team" / "check_compatibility.py").read_text(encoding="utf-8")
        self.assertIn('"VERSION.json"', script)
        self.assertIn('PROJECT_ROOT.glob("VERSION_V*.json")', script)
        for sensitive in ("credentials.md", "记忆账本.json", "LLM配置.json"):
            self.assertIn(sensitive, script)

    def test_complete_history_contract_is_present(self):
        history_root = ROOT / "AI-Team" / "history"
        self.assertTrue((history_root / "README.md").is_file())
        manifest = json.loads((history_root / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn(manifest["schema"], (1, 2))
        self.assertIsInstance(manifest["workspaces"], list)
        version_notes = (ROOT / "AI-Team" / "versions" / "V4.2.md").read_text(encoding="utf-8")
        for phrase in ("项目工单", "dist", ".git", "缓存", "Portable-AI-Team/"):
            self.assertIn(phrase, version_notes)

    def test_status_card_and_team_json_capsule_ids_match(self):
        if not (ROOT / "团队状态.json").exists():
            self.skipTest("母版不持有 团队状态.json；项目胶囊启用后才有")
        team = load_unique_json(ROOT / "AI-Team" / "team.json")
        status = load_unique_json(ROOT / "团队状态.json")
        self.assertEqual(status["capsule_id"], team["capsule_id"])
        self.assertEqual(status["capsule_id"], "portable-ai-team-20261010-v3")

    def test_agent_d_sources_and_bridges_are_registered(self):
        team_py = (ROOT / "AI-Team" / "team.py").read_text(encoding="utf-8")
        capsule_py = (ROOT / "AI-Team" / "capsule.py").read_text(encoding="utf-8")
        for phrase in (
            ".codex/agents/agent-d.toml",
            ".agents/agents/agent-d/agent.md",
        ):
            self.assertIn(phrase, team_py)
            self.assertIn(phrase, capsule_py)
        self.assertTrue((ROOT / "AI-Team/bridges/codex/agent-d.toml").is_file())
        self.assertTrue((ROOT / "AI-Team/bridges/antigravity/agent-d.md").is_file())
        self.assertTrue((ROOT / "AI-Team/adapters/trae/AgentD-import.md").is_file())

    def test_v31_platform_adapters_and_onboarding_are_registered(self):
        # v3.1 adds Claude Code and WorkBuddy bridges plus LLM onboarding docs.
        for relative in (
            "AI-Team/bridges/claude/claude.md",
            "AI-Team/bridges/workbuddy/portable-ai-team.md",
            "AI-Team/ide-guides/claude-code.md",
            "AI-Team/ide-guides/workbuddy.md",
            "AI-Team/references/llm-接入指南.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        matrix = (ROOT / "AI-Team/ide-guides/compatibility-matrix.md").read_text(encoding="utf-8")
        for phrase in ("Claude Code", "WorkBuddy", "五平台"):
            self.assertIn(phrase, matrix)
        capsule_py = (ROOT / "AI-Team/capsule.py").read_text(encoding="utf-8")
        for phrase in ("workbuddy-rule", "claude_block", "doctor"):
            self.assertIn(phrase, capsule_py)
        with (ROOT / "AI-Team/bridges/codex/agent-d.toml").open("rb") as stream:
            data = tomllib.load(stream)
        self.assertEqual(data["name"], "agent-d")
        self.assertNotIn("model", data)

    def test_documents_describe_v3_features_without_real_keys(self):
        for name in ("README.md", "START-HERE.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in ("AgentD", "外部 API", "并行派单", "失败降级", "codex_builtin"):
                self.assertIn(phrase, text, f"{name}: {phrase}")
            self.assertNotIn("Bearer ", text)
            self.assertIn("memory-20261010", text)

    def test_llm_config_has_only_structural_fields_checked(self):
        # Read only the expected structure, not the secret value.
        config_path = ROOT / "LLM配置.json"
        if not config_path.is_file():
            self.skipTest("LLM配置.json is machine-local; configure it to run this check")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertIsInstance(config.get("enabled"), bool)
        self.assertIsInstance(config.get("models"), dict)
        self.assertIsInstance(config.get("routing"), dict)
        self.assertGreaterEqual(config.get("max_parallel"), 1)
        self.assertLessEqual(config.get("max_parallel"), 4)
        self.assertEqual(config.get("fallback"), "codex_builtin")
        self.assertGreater(config.get("timeout_seconds"), 0)
        # Deliberately do not inspect, copy, or print api_key.


if __name__ == "__main__":
    unittest.main()
