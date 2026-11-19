# Redstone Music Pipeline

新 agent 从 [START_HERE](START_HERE.md) 与专业 Skill 入手。本文保留底层构建/任务合同说明；新增音乐、声音、建筑、证据工具见 [CLI 工具参考](docs/TOOL_REFERENCE.md)。

实际已跑的测试与边界见 [v0.1 验证记录](PIPELINE_VERIFICATION.md)。

产品目标和取舍见[正式改写方案](docs/REWRITE_PLAN.md)，经验依据见[Nevada正式复盘](docs/NEVADA_RETROSPECTIVE.md)。当前实施与验证范围见[实施记录](docs/IMPLEMENTATION_STATUS.md)。

最快试跑：`python run_pipeline.py demo`。重复运行会复用未改变且完整的产物，不覆盖旧版本。系统不会把技术检查当作已经听审、录制或投稿。

A local, resumable production pipeline for Minecraft Java note-block performances. It turns a MIDI master into a physical redstone machine, a playable world, a Litematica schematic, synchronized visual assets and a versioned delivery bundle.

The conductor runs deterministic tools and hands creative or repair work to specialist agents through constrained task files. It does not require an API key or send your music to a cloud model.

## Quick start

Requires Python 3.12+, Node.js 24+ and the Python dependencies below. Professional tools use `.[production]`, optional melody transcription uses `.[pitch]`. Minecraft files are unnecessary for generating and checking a candidate world; real game replay requires a separate, locally supplied Java 1.21.1 environment.

```shell
python -m pip install -e .
python -m redstone_music doctor
python -m redstone_music init projects/demo --title "Original demo" --midi examples/demo.mid
python -m redstone_music run projects/demo
python -m redstone_music status projects/demo
```

`examples/demo.mid` is an original synthetic eight-second phrase, not a commercial song excerpt. Run these commands from a source checkout. In a wheel-only installation, pass your own MIDI path instead.

The final stage returns the release artifact location. Its `deliverables.zip` contains the playable world, control data pack, `.litematic`, instructions and a manifest. A custom sound pack and compiled client mod are included only when explicitly supplied or successfully built.

Run the same command again to resume or reuse verified stage artifacts. Modify project configuration or inputs and only the affected stages and their dependants rebuild. Use a new project directory for a new song; initialization refuses to overwrite an existing project.

## Production stages

| Stage | Work | Main outputs |
|---|---|---|
| `music` | Read the MIDI tempo map, sustain pedal and note boundaries, or import an explicitly approved event baseline | `score.json`, source hashes, unchanged `master.mid` when supplied |
| `sound` | Map musical roles to note-block timbres/ranges and add tagged sustain retriggers where appropriate | `events.json`, adaptation report, optional `resources.zip` |
| `machine` | Compile even/odd physical redstone lanes, lights, controls, smooth-follow camera and reset/loading logic | Playable Anvil world, `performance.litematic`, helper data pack, expected events |
| `visuals` | Produce onset-driven effects, sections and fixed-screen captions; optionally compile the Fabric client | Visual score, captions, optional `client.jar` |
| `validate` | Independently decode Anvil and Litematica exports, reconcile source/event/block/visual contracts and bind evidence to hashes | Validation report with explicit static/runtime boundaries |
| `release` | Verify the validated files are unchanged, then package the explicit deliverables | `deliverables.zip`, manifest and usage instructions |

Build through an intermediate stage:

```shell
python -m redstone_music run projects/demo --until sound
```

Stage outputs are immutable, fingerprinted directories under `artifacts/`. The project owns its state, staging directory and exclusive run lock. The fingerprints include source content, relevant configuration, implementation dependencies and upstream artifacts. Failed or damaged artifacts cannot grant a cached pass. `--force` explicitly rebuilds the requested chain.

## Main agent and specialist handoffs

The main agent owns the goal, configuration, schedule and acceptance decisions. Specialist roles are `music`, `sound`, `machine`, `visuals` and `quality`. Specialists submit artifacts and evidence; they cannot grant their own stage a pass or replace the conductor's state.

With no music input, the conductor creates a music-production task instead of inventing a complete song or marking the stage complete:

```shell
python -m redstone_music init projects/new-song --title "New song" --reference-audio path/to/reference.mp3
python -m redstone_music run projects/new-song
python -m redstone_music tasks projects/new-song
```

To request an additional review or repair:

```shell
python -m redstone_music create-task projects/demo --role sound --objective "Review sustained lead clarity and provide an improved sound candidate"
```

Each task directory contains `TASK.md`, `task.json` and a permitted `output/` directory. Use the actual task ID returned by the command:

```shell
python -m redstone_music claim-task projects/demo TASK_ID --agent sound-specialist
python -m redstone_music complete-task projects/demo TASK_ID --result tasks/TASK_ID/result.json
python -m redstone_music run projects/demo
```

`--result` is relative to the project directory. The specialist reads the task's contract, writes outputs below that task's `output/`, and writes `result.json` in the task directory. Review results include a summary, evidence and limitations. A review response can look like:

```json
{
  "outputs": {"review": "tasks/TASK_ID/output/review.json"},
  "configPatch": {"sound": {"retrigger": false}},
  "notes": "Compared the candidate's onset and sustain rendering; client listening remains pending."
}
```

The accompanying `review.json` has `summary`, `evidence` and `limitations` fields. Follow the generated contract for permitted inputs and configuration domains. A music-import task requires a valid MIDI output. Sound and caption resources can be imported only by roles allowed to supply them. Changed inputs make old task responses stale. Completion imports constrained artifacts and configuration; the next `run` rebuilds and independently validates them.

The CLI creates and validates task handoffs. The host agent system decides whether to dispatch them to local subagents or another tool. This project does not silently start paid model calls, bypass a login, or claim that a task was performed merely because its prompt was generated.

## Configuration

`project.json` is created by `init`. Paths in `inputs` may be absolute or relative to the project. Useful options include:

```json
{
  "inputs": {
    "midi": "sources/master.mid",
    "approvedEvents": null,
    "referenceAudio": null,
    "soundPack": null,
    "captions": null
  },
  "sound": {"profile": "vanilla", "retrigger": true},
  "machine": {"decorate": true},
  "visuals": {"enabled": true},
  "runtime": {"serverValidation": false},
  "policy": {"maxAttempts": 2, "maxDurationSeconds": 900, "maxNotes": 50000, "maxInputMiB": 256}
}
```

This is an excerpt: retain the generated `schemaVersion`, `slug` and `title`. `referenceAudio` is context for a specialist, not an automatic transcription switch. The importer supports a standard MIDI master or an approved event JSON; it does not automatically acquire copyrighted music or restore an arbitrary recording perfectly.

For custom timbres, supply a compatible sound resource ZIP and select a non-vanilla profile. A resource pack does not itself change physical instrument bases; an approved baseline or suitable adaptation must agree with those mappings. Range changes and approximations remain disclosed in the sound report.

Caption input is a JSON object with `cues`. Each cue has a unique `id`, integer music-tick `begin`/`end`, text and optional fixed-screen layout/effect fields. One tick is 50 ms. The pipeline rejects caption timing outside the performance.

## Visual client and real game validation

Without a client compilation environment, the pipeline still generates music-bound visual/caption assets and labels the missing client build. It does not pretend these JSON files alone produce rendered effects. `runtime.clientRuntime` can point to a local runtime JSON containing a Java 21 JDK and the matching Fabric/intermediary compilation classpath. Game assets and dependency JARs are not distributed here.

The physical machine targets Java 1.21.1 and the included, previously developed even/odd timing template. New game versions, unbounded polyphony and multiplayer synchronization are outside the verified template. Unsupported event roles or capacity fail explicitly.

Optional server replay uses trusted local paths for `runtime.java`, `serverJar`, `traceAgent`, `traceHook` and `asmJar`, plus `serverValidation: true`. The operator must review and accept the Minecraft EULA before enabling `acceptEula`. The test uses a copied world and its own process. No server or trace JAR is bundled in this repository.

Build the optional test observer from the included Java sources with `python run_pipeline.py build-trace --jdk /path/to/jdk21 --asm /path/to/asm.jar --out local-trace`. Use a local ASM dependency from its official distribution or Maven repository. This observer records successful note-block events; it does not replace redstone with command-based sound.

Generated files and successful export readback establish **static validation**. Real server playback, client interpolation/rendering, actual listening, capture performance and artistic acceptance are separate. Reports never upgrade static checks into game or listening evidence. The default result is a candidate ready for actual game review, not an automatically certified finished video.

## Tests and development

```shell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Tests cover MIDI timing and pedal semantics, invalid music, artifact invalidation, task boundaries, export decoding, corrupted data, release integrity and an original-MIDI-to-delivery integration. A private Nevada regression skips when its original assets are absent; public tests use synthetic data. Tests requiring Node explicitly skip when it is unavailable, while CI installs Node.

## Open-source scope

Code, templates and rendering sources are licensed under MIT; see [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md). Reference songs, stems, third-party sound fonts/textures/shaders, Minecraft binaries, user profiles, caches and generated private projects are excluded. The public source repository does not provide rights to those materials.
