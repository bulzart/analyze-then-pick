# /analyze-then-pick

A Claude Code slash command that studies a folder of reference videos (or takes videos to edit), learns what makes
them work, and produces new vertical 9:16 720p videos through the Higgsfield MCP. Prompts follow each model's own
structure. Every video is then assembled as an editable CapCut project.

This repository is the **2026-10-14 version, the last one before Loupe**: the router command, the 19 `atp-*` phase skills,
the sectioned references and model guides, and the scripts. It has no Loupe web app, no Loupe hooks and no QC keeper.
Flags go to the self-contained page `analyze-then-pick/caught_flags.html`.

## What is in here

```
claude/                          copied into your Claude Code home (~/.claude) by the installer
├── commands/analyze-then-pick.md      the router (~13 KB): arguments, resume, loading rules, contract, phase map
├── skills/atp-*/SKILL.md              19 phase skills (start → prepare → study → create|recreate plan → asset plan → produce → wrap-up,
│                                      per-video: plan → write request → inputs → precheck → submit → postprocess → QC → record)
└── analyze-then-pick/
    ├── README.md                      the library's own guide: organisation, editing, adding/updating a model
    ├── config.json                    paths, fixed 9:16/720p output, analysis defaults, CapCut store + house text style
    ├── models/                        one engineering guide per Higgsfield video model (index + section files), models/index.json
    ├── higgsfield/                    the Higgsfield MCP guide, catalog snapshot, first-party recipes
    ├── reference/                     analysis protocol, generation system, anomaly catalog, creative direction, brand guardrails,
    │                                  text and format, CapCut assembly, production agents, assets and substitution
    ├── pipeline/preprocessing.md      the local FFmpeg-first preprocessing pipeline
    └── scripts/                       atp.py (the local toolkit), docs_tool.py (section tool + check), caught_flags_template.html
build-prompt/analyze-then-pick.txt     the build prompt this version was generated from (the spec of the whole pipeline)
vendor/capcut-mcp/                     the CapCut MCP server the pipeline edits with (MIT, Gusmares/MCP-CapCut fork, see PROVENANCE.md)
install.py / install.ps1 / install.sh  the installer
```

`claude/` is byte-identical to the original build (first commit of this repo). Only run data was left out (the flag
record and a config backup). The installer rewrites the build machine's absolute paths (`C:/Users/Glaresquare1/...`)
to yours while it copies.

## Requirements

| Need | Notes |
|---|---|
| Claude Code | the CLI, signed in |
| A Higgsfield account with credits | every generation is paid; the pipeline asks before spending above the cost gate in `config.json` |
| Python 3.10+ | 3.12 used to build it; Pillow, NumPy, requests (installed for you); optional: faster-whisper, rapidocr-onnxruntime, librosa |
| FFmpeg + ffprobe | Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` |
| Node.js 18+ and npm | for the CapCut MCP server and capcut-cli |
| CapCut desktop 9.x | 10.x is refused by capcut-cli's write guard; CapCut must be closed while a project is written |
| capcut-cli 0.25.0 | `npm install -g capcut-cli@0.25.0` (the installer does it) |

The pipeline was built and run on **Windows** (some steps call PowerShell). macOS should work for most steps but has not been tested.

## Install

```powershell
git clone https://github.com/<owner>/analyze-then-pick.git
cd analyze-then-pick
powershell -ExecutionPolicy Bypass -File install.ps1      # Windows
# bash install.sh                                          # macOS / Linux / Git Bash
```

The installer:
1. copies the command, the skills and the library into `~/.claude` and rewrites the paths for your machine;
2. installs the CapCut MCP server at `~/.claude/analyze-stack/tools/mcp/capcut-mcp` and runs `npm install`;
3. registers the MCP servers at user scope (skipped when already registered):
   - `claude mcp add --scope user --transport http higgsfield https://mcp.higgsfield.ai/mcp`
   - `claude mcp add --scope user capcut -e CAPCUT_DRAFTS_DIR=<your CapCut draft store> -e CAPCUT_TEMPLATE_DRAFT=_analyze-stack-template -- node <capcut-mcp>/src/server.js`
4. installs the Python packages and capcut-cli;
5. checks the tools and runs `docs_tool.py check`, which should report `0 errors`.

Options: `--force` replaces an existing install (the old files move to `~/.claude-atp-backup-<stamp>/` and its `runs/`
folder is carried over), `--no-deps`, `--no-mcp`, `--dry-run`, `--python <exe>`, `--capcut-drafts <dir>`, `--claude-home <dir>`.

Then open Claude Code, run `/mcp`, and sign in to **higgsfield**.

## The CapCut template draft

The CapCut MCP builds valid CapCut JSON by cloning segments out of an existing draft, so the pipeline needs one draft named
**`_analyze-stack-template`** in your CapCut draft store. Make it once:

1. Open CapCut desktop and create a new project at **9:16** (1080×1920, 30 fps).
2. Add a short video clip, a text layer, an audio clip, and a transition between two clips.
3. Rename the project to `_analyze-stack-template` and close CapCut.

Each run clones it with `empty: true`, so its media are never used. Don't edit or delete it afterwards.
Draft store: Windows `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`, macOS `~/Movies/CapCut/User Data/Projects/com.lveditor.draft`
(if yours is elsewhere, pass `--capcut-drafts`).

## Use

```
/analyze-then-pick analyze <references-folder> assets <asset files/folders…> [examples <folder>]
/analyze-then-pick edit <video files/folders…> [examples <folder>]
/analyze-then-pick resume [run-dir]
```

- **Analyze Mode** reads the reference videos frame by frame (5 fps adaptive), works out what makes them work, and
  plans the new videos: Recreate (picked references, edited) or Create (new concepts from the references' craft).
  Each video is then produced end to end by its own agent, at most 5 at once.
- **Edit Mode** edits the given videos one at a time, with a review after each edit.
- At the start you pick one video model from a menu of every Higgsfield model available. That model stays locked for the whole run.
- Every run lives in `~/.claude/analyze-then-pick/runs/<stamp>-<slug>/`. `state.json` makes it resumable at any phase boundary.
- Finished videos go into the run's `deliverables/` folder, plus one CapCut project per video named `DD_Mon_YYYY_vNN`.

The command is never run as a Workflow and the model can't invoke it on its own (`disable-model-invocation: true`).
You start it yourself.

## Maintaining it

See `claude/analyze-then-pick/README.md` (installed at `~/.claude/analyze-then-pick/README.md`): edit the skill or
section that owns a step, then run `python ~/.claude/analyze-then-pick/scripts/docs_tool.py check` (it must report
0 errors). New models come from `models/_TEMPLATE.md`, which `docs_tool.py split` turns into section files. That
README also mentions `/update-from-errors` and `Documents/prompts/...`. Both are tools from the original author's
setup and are not part of this repository.
