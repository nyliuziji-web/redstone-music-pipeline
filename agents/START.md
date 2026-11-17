# Main agent: produce a redstone music performance

For production-kit development, read [the rewrite plan](../docs/REWRITE_PLAN.md) and [Nevada lessons](../docs/NEVADA_RETROSPECTIVE.md). Their proposed skills and interfaces are not implemented CLI features. The default collaboration is autonomous agent work with user listening/viewing at representative samples and final delivery.

Use the executable pipeline. Start with `python run_pipeline.py doctor` and read `PIPELINE.md`. For a new song, initialize a new project with a user-supplied MIDI master or a brief/reference. Never reuse a previous song's project directory.

1. Run the project. Successful stages are immutable, hashed and reusable. Read the returned `releasePath`, warnings and validation boundaries.
2. If the project is `awaiting_agent` or a stage fails, inspect `tasks/<id>/task.json`, `prompt.md`, the failed staging diagnostics, and current `state.json`.
3. Delegate the task to the matching professional role when delegation is authorized and available. Give only the project contract, task, relevant inputs and the role guide in this directory. Avoid passing unrelated conversations or permitting shared artifact edits. If delegation is unavailable, perform the role yourself using the same result contract.
4. Claim the task; the specialist writes only to its designated `output/` directory, including a JSON result matching `resultContract`. The main agent calls `complete-task` and then reruns the pipeline. Task completion never grants technical validation.
5. A required engine change is implemented in source, tested, then rerun. Do not force an unsupported idea through the narrow configPatch interface or delete assertions to make a stage pass.
6. Independent quality review uses exported bytes and actual evidence. Technical success must not be relabeled as artistic approval, actual recording or publication.

Roles: [music](music.md), [sound](sound.md), [machine](machine.md), [visuals](visuals.md), [quality](quality.md).

Only the main agent edits the project contract or integrates competing proposals. Specialists do not modify committed artifacts, other tasks' files, installed game profiles or remote repositories. Keep compatible independent work parallel; operations on one project and a test process remain exclusive. Respect the configured attempt and resource budgets; report a concrete external blocker when it cannot be solved within the available tools.

The file adapter works with agent environments such as Codex/ChatGPT. The Python process does not secretly invoke cloud models or create subagents itself. The main agent uses its environment's delegation capability; deterministic work is executed locally without a model call.
