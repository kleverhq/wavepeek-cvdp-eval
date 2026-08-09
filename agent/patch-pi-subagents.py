#!/usr/bin/env python3
"""Disable project-local configuration discovery in the pinned extension."""

from pathlib import Path

ROOT = Path("/opt/pi-subagents/src")
REPLACEMENTS = {
    "settings.ts": (
        'return { ...readSettingsFile(globalPath()), ...readSettingsFile(projectPath(cwd)) };',
        'return readSettingsFile(globalPath());',
    ),
    "custom-agents.ts": (
        '''  loadFromDir(globalDir, agents, "global");            // lowest priority
  loadFromDir(workspaceProjectDir, agents, "project"); // shared workspace
  loadFromDir(projectDir, agents, "project");          // highest priority (overwrites)''',
        '''  loadFromDir(globalDir, agents, "global");''',
    ),
    "agent-runner.ts": (
        'const configCwd = options.configCwd ?? effectiveCwd;',
        'const configCwd = process.env.PI_SUBAGENTS_CONFIG_CWD ?? options.configCwd ?? effectiveCwd;',
    ),
    "agent-runner.ts#thinking": (
        'const thinkingLevel = options.thinkingLevel ?? agentConfig?.thinking;',
        'const thinkingLevel = undefined;',
    ),
}

for name, (old, new) in REPLACEMENTS.items():
    path = ROOT / name.split("#", 1)[0]
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"unexpected pinned pi-subagents source: {name}")
    path.write_text(text.replace(old, new))
