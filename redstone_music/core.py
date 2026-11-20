"""Local orchestration, immutable artifacts and file-based specialist handoffs.

Only the static stage registry can execute code. Project JSON cannot supply shell
commands, Python modules, or code. Modules receive an exclusive staging directory.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
import ctypes
import hashlib
import importlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import time
import uuid

STAGES = ("music", "sound", "machine", "visuals", "validate", "release")
DEPENDENCIES = {
    "music": (), "sound": ("music",), "machine": ("sound",),
    "visuals": ("music", "sound", "machine"),
    "validate": ("music", "sound", "machine", "visuals"),
    "release": ("music", "sound", "machine", "visuals", "validate"),
}
DOMAINS = {
    "music": ("music",), "sound": ("sound",),
    "machine": ("machine", "layout", "runtime"), "visuals": ("visuals", "runtime"),
    "validate": ("runtime", "validation"), "release": ("publishing", "policy"),
}
STAGE_INPUTS = {
    "music": ("midi", "approvedEvents", "referenceAudio"),
    "sound": ("soundPack", "soundProfile", "adaptationPlan"), "machine": ("stageModule",), "visuals": ("captions", "showScore"),
    "validate": (), "release": (),
}
REPO_ROOT = Path(__file__).resolve().parent.parent
_IMPORTED_SOURCE_HASHES = {}
_CORE_IMPORT_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class PipelineError(RuntimeError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def hash_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".tmp-" + uuid.uuid4().hex[:12])
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _rename_artifact(source, destination):
    """Keep atomic promotion intact when Windows briefly holds a directory."""
    for delay in (0, .10, .25, .50, 1.0):
        if delay:
            time.sleep(delay)
        try:
            source.rename(destination)
            return
        except OSError as error:
            if (getattr(error, 'winerror', None) not in {5, 32, 33}
                    or destination.exists() or not source.exists() or delay == 1.0):
                raise


def owned(project, relative):
    project = Path(project).resolve()
    candidate = project / relative
    resolved = candidate.resolve()
    if resolved == project or not resolved.is_relative_to(project):
        raise PipelineError(f"Project output escapes project: {relative}")
    return candidate


def source_path(project, value):
    if not isinstance(value, str) or not value or any(c in value for c in ("\r", "\n", "\0")):
        raise PipelineError("Input paths must be nonempty strings")
    p = Path(value).expanduser()
    return (Path(project) / p).resolve() if not p.is_absolute() else p.resolve()


def validate_slug(slug):
    reserved = {"con", "prn", "aux", "nul"} | {f"{a}{i}" for a in ("com", "lpt") for i in range(1, 10)}
    if not isinstance(slug, str) or len(slug) > 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in reserved:
        raise PipelineError("slug must be lowercase letters/digits separated by single hyphens (max 64)")


def load_config(project):
    project = Path(project).resolve(strict=True)
    config = read_json(owned(project, "project.json"))
    if not isinstance(config, dict) or config.get("schemaVersion") != 1:
        raise PipelineError("Unsupported project schemaVersion")
    validate_slug(config.get("slug"))
    if not isinstance(config.get("inputs"), dict):
        raise PipelineError("project.inputs must be an object")
    if not isinstance(config.get("title"), str) or not config["title"].strip():
        raise PipelineError("project.title is required")
    if len(config['title']) > 256 or any(c in config['title'] for c in ('\r', '\n', '\0')):
        raise PipelineError('Project title must be a single line of at most 256 characters')
    for key, value in config['inputs'].items():
        if value is not None:
            source_path(project, value)
    for key, value in config.get('runtime', {}).items():
        if isinstance(value, str) and any(c in value for c in ('\r', '\n', '\0')):
            raise PipelineError(f'Runtime value {key} contains control characters')
    policy = config.get('policy', {})
    for key, default, maximum in [('maxAttempts', 2, 20), ('maxDurationSeconds', 900, 7200),
                                   ('maxNotes', 50000, 200000), ('maxInputMiB', 256, 1024)]:
        value = policy.get(key, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise PipelineError(f'policy.{key} must be an integer in 1..{maximum}')
    return config


def initialize(project, title=None, midi=None, approved_events=None, slug=None, reference_audio=None):
    project = Path(project).resolve()
    slug = slug or project.name
    validate_slug(slug)
    if project.exists():
        raise PipelineError("Refusing to overwrite existing project directory")
    config = {
        "schemaVersion": 1, "slug": slug, "title": title or slug,
        "inputs": {"midi": str(Path(midi).resolve()) if midi else None,
                   "approvedEvents": str(Path(approved_events).resolve()) if approved_events else None,
                   "referenceAudio": str(Path(reference_audio).resolve()) if reference_audio else None,
                   "soundPack": None, "captions": None,
                   "soundProfile": None, "adaptationPlan": None, "stageModule": None, "showScore": None},
        "sound": {"retrigger": True, "profile": "vanilla", "adapter":"role-consistent", "consistency":"role"},
        "machine": {"decorate": True}, "visuals": {"enabled": True},
        "runtime": {"serverValidation": False, "java": None, "serverJar": None,
                    "traceAgent": None, "acceptEula": False},
        "policy": {"maxAttempts": 2, "maxDurationSeconds": 900, "maxNotes": 50000, "maxInputMiB": 256},
    }
    for key in ("midi", "approvedEvents", "referenceAudio"):
        if config["inputs"][key] and not Path(config["inputs"][key]).is_file():
            raise PipelineError(f"Missing {key} input")
    project.mkdir(parents=True, exist_ok=False)
    for name in ("artifacts", ".staging", "tasks", "sources", "reviews", "evidence"):
        owned(project, name).mkdir()
    atomic_json(project / "project.json", config)
    atomic_json(project / "state.json", {"schemaVersion": 1, "stages": {}, "status": "initialized"})
    (project / 'brief.md').write_text('# 作品需求\n\n' + config['title'] + '\n\n反馈约定：agent自主推进，代表样段与最终成品请用户听看。\n', encoding='utf-8')
    (project / 'plan.md').write_text('# 制作计划\n\n1. 体检实际素材并建立角色/段落。\n2. 代表样段双试听及视觉预览。\n3. 按反馈修订、冻结、扩展全曲。\n4. 实际游戏、成片与交付验收。\n\n下一步：运行 capabilities 与 inspect-source；需要创作时读取对应 Skill。\n', encoding='utf-8')
    atomic_json(project / 'source-manifest.json', {'schemaVersion': 1, 'sources': [
        {'kind': key, 'path': value, 'sha256': hash_file(value), 'provenance': 'operator supplied', 'rights': 'operator must record source rights'}
        for key, value in config['inputs'].items() if value]})
    return {"project": str(project), "status": "initialized", "config": config}


def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return True
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return ctypes.get_last_error() != 87  # invalid PID, otherwise fail closed
        try:
            return kernel.WaitForSingleObject(handle, 0) != 0
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def project_lock(project):
    path = owned(project, ".pipeline.lock")
    token = uuid.uuid4().hex
    record = {"pid": os.getpid(), "host": socket.gethostname(), "token": token, "created": time.time()}
    for _ in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(record, stream)
            break
        except FileExistsError:
            try:
                previous = read_json(path)
            except (OSError, ValueError):
                raise PipelineError("Unreadable project lock; inspect before removing it")
            if previous.get("host") != socket.gethostname() or pid_alive(previous.get("pid")):
                raise PipelineError(f"Project already locked by PID {previous.get('pid')}")
            # Recheck identity: never remove a lock another process replaced.
            if read_json(path).get("token") != previous.get("token"):
                raise PipelineError("Project lock changed during stale-lock recovery")
            path.unlink()
    else:
        raise PipelineError("Could not obtain project lock")
    try:
        yield
    finally:
        try:
            if read_json(path).get("token") == token:
                path.unlink()
        except FileNotFoundError:
            pass


def file_map(directory):
    directory = Path(directory)
    files = {}
    for p in sorted(directory.rglob("*")):
        if p.is_symlink():
            raise PipelineError(f"Artifact cannot contain symbolic links: {p}")
        if p.is_file() and p != directory / "stage_manifest.json":
            if not p.resolve().is_relative_to(directory.resolve()):
                raise PipelineError("Artifact file escapes directory")
            files[p.relative_to(directory).as_posix()] = {"bytes": p.stat().st_size, "sha256": hash_file(p)}
    return files


def artifact_valid(path, record):
    try:
        manifest = read_json(Path(path) / "stage_manifest.json")
        return (manifest["fingerprint"] == record["fingerprint"]
                and digest(manifest) == record["manifestSha256"]
                and manifest["files"] == file_map(path))
    except (OSError, ValueError, KeyError, PipelineError):
        return False


def _module_sources(module):
    """Hash local Python imports recursively; explicit assets use DEPENDENCY_FILES."""
    package = Path(__file__).resolve().parent
    found, pending = {}, [Path(module.__file__).resolve()]
    while pending:
        path = pending.pop()
        if path in found or not path.is_file():
            continue
        found[path] = hash_file(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (ValueError, SyntaxError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                if node.level == 1 and node.module:
                    names = [node.module]
                elif node.module and node.module.startswith("redstone_music."):
                    names = [node.module.split(".", 1)[1]]
                elif node.level == 1:
                    names = [x.name for x in node.names]
            elif isinstance(node, ast.Import):
                names = [x.name.split(".", 1)[1] for x in node.names if x.name.startswith("redstone_music.")]
            for name in names:
                dependency = package / (name.replace(".", "/") + ".py")
                if dependency.is_file():
                    pending.append(dependency)
    return {str(p.relative_to(package)): h for p, h in found.items() if p.is_relative_to(package)}


def input_fingerprint(project, config, stage, dependencies, module=None, override=None):
    if hash_file(__file__) != _CORE_IMPORT_HASH:
        raise PipelineError('Conductor source changed in this process; restart the CLI before continuing')
    selected = {"schemaVersion": config["schemaVersion"], "slug": config["slug"], "title": config["title"]}
    selected.update({key: config.get(key) for key in DOMAINS[stage]})
    if stage in ('music', 'sound', 'machine'):
        selected['budgets'] = {key: config.get('policy', {}).get(key, default) for key, default in
                              [('maxDurationSeconds', 900), ('maxNotes', 50000), ('maxInputMiB', 256)]}
    inputs = {}
    for key in STAGE_INPUTS[stage]:
        value = config["inputs"].get(key)
        if value:
            path = source_path(project, value)
            if not path.is_file():
                raise PipelineError(f"Missing input {key}: {path}")
            if path.stat().st_size > config.get('policy', {}).get('maxInputMiB', 256) * 1024 ** 2:
                raise PipelineError(f'Input {key} exceeds configured maxInputMiB')
            inputs[key] = {"path": str(path), "sha256": hash_file(path)}
    if override:
        try:
            sources = {"override": hashlib.sha256(inspect.getsource(override).encode()).hexdigest()}
        except (OSError, TypeError):
            sources = {"override": hashlib.sha256(override.__code__.co_code).hexdigest()}
    else:
        sources = _module_sources(module)
        # CLI invocations start fresh. A long-lived conductor must not hash new
        # source while executing an already-imported old function implementation.
        package = Path(__file__).resolve().parent
        for relative, value in sources.items():
            key = str(package / relative)
            previous = _IMPORTED_SOURCE_HASHES.setdefault(key, value)
            if previous != value:
                raise PipelineError('Loaded stage source changed in this process; restart the CLI before continuing')
        context = {"project": str(project), "root": str(REPO_ROOT), "config": config}
        assets = list(getattr(module, "DEPENDENCY_FILES", ()))
        hook = getattr(module, "fingerprint_inputs", None)
        if hook:
            assets.extend(hook(context))
        for asset in assets:
            p = Path(asset)
            p = (REPO_ROOT / p).resolve() if not p.is_absolute() else p.resolve()
            if not p.is_file():
                raise PipelineError(f"Missing stage dependency: {p}")
            sources[str(p)] = hash_file(p)
    sources["core.py"] = hash_file(__file__)
    return digest({"stage": stage, "config": selected, "inputs": inputs, "sources": sources,
                   "dependencies": dependencies})


ROLES = ("music", "sound", "machine", "visuals", "quality", "producer", "arrangement", "stage")
ROLE_SKILLS = {'music':'music-director','sound':'sound-designer','machine':'redstone-engineer',
               'visuals':'show-director','quality':'verify-and-deliver','producer':'redstone-producer',
               'arrangement':'noteblock-arranger','stage':'stage-designer'}
ROLE_DOMAINS = {"music": {"music"}, "sound": {"sound"}, "machine": {"machine", "layout"},
                "visuals": {"visuals"}, "quality": {"validation", "runtime"},
                "producer": set(), "arrangement": {"sound"}, "stage": {"machine"}}
ROLE_IMPORTS = {"music": {"midi", "adaptationPlan"}, "sound": {"soundPack", "soundProfile"}, "machine": {"stageModule"},
                "visuals": {"captions", "showScore"}, "quality": set(), "producer": set(),
                "arrangement": {"adaptationPlan", "soundProfile"}, "stage": {"stageModule"}}
TASK_KINDS = {"review": {"review"}, "music_import": {"midi"},
              "arrangement": {"adaptationPlan", "review"},
              "sound_profile": {"soundProfile", "soundPack", "review"},
              "show_score": {"showScore", "review"}, "stage_module": {"stageModule", "review"},
              "engine_change": {"review", "proposal"}}


def _request_signature(project, config, include_artifacts=True):
    data = {"config": config, "files": {}}
    for key, value in config["inputs"].items():
        if value:
            p = source_path(project, value)
            data["files"][key] = hash_file(p) if p.is_file() else "missing"
            if key == 'soundProfile' and p.is_file():
                from .music_tools import sound_profile_dependencies
                try:
                    data['files']['soundProfileResources'] = {str(f): hash_file(f) if f.is_file() else 'missing'
                        for f in sound_profile_dependencies(p)}
                except (ValueError,OSError,TypeError,KeyError) as error:
                    # A broken profile must still be representable in a repair task.
                    data['files']['soundProfileResources'] = {'invalid':str(error)}
    # Include materialized artifacts, not mutable run timestamps or task state.
    state_path = owned(project, "state.json")
    state = read_json(state_path) if state_path.exists() else {}
    if include_artifacts:
        data["artifacts"] = {key: value["fingerprint"] for key, value in state.get("stages", {}).items()
                             if value.get("status") == "passed"}
    return digest(data)


def create_music_task(project, config):
    return _create_task(project, config, "music", "Create a complete MIDI master from the project references", "music_import")


def _create_task(project, config, role, objective, mode="review"):
    if role not in ROLES:
        raise PipelineError("Unknown specialist role")
    if mode not in TASK_KINDS or not (TASK_KINDS[mode] - {'review', 'proposal'}) <= ROLE_IMPORTS[role]:
        raise PipelineError('Task kind is unsupported for this role')
    signature = _request_signature(project, config)
    task_id = role + "-" + digest({"input": signature, "objective": objective, "mode": mode})[:16]
    folder = owned(project, "tasks/" + task_id)
    task_file = folder / "task.json"
    if task_file.exists():
        return read_json(task_file)
    folder.mkdir(parents=True)
    (folder / "output").mkdir()
    from .kit import resource_root
    skill = resource_root() / 'skills' / ROLE_SKILLS[role] / 'SKILL.md'
    task = {"schemaVersion": 1, "id": task_id, "role": role, "mode": mode, "status": "pending",
            'skill':str(skill),'skillSha256':hash_file(skill),
            "inputFingerprint": signature, "createdAt": time.time(),
            "allowedOutput": str(folder / "output"), "agent": None,
            "objective": objective,
            "project": str(project), "references": config["inputs"],
            "allowedConfigDomains": sorted(ROLE_DOMAINS[role]),
            "allowedInputImports": sorted(ROLE_IMPORTS[role]),
            "resultContract": {"outputs": {key: f"tasks/{task_id}/output/" +
                ({'midi': 'master.mid', 'soundPack': 'resources.zip'}.get(key, key + '.json')) for key in sorted(TASK_KINDS[mode])},
                               "configPatch": {}, "notes": "provenance, changes, uncertainties and listening scope"}}
    atomic_json(task_file, task)
    (folder / "TASK.md").write_text(
        f"# {role} specialist task\n\n{objective}\n\nRead {skill}, project.json, state.json and task.json. "
        "Inspect the corresponding stage artifacts and production skill. Write only to this task's output/. "
        "Return result.json inside the task directory with the resultContract fields. "
        "For a review provide review.json: {summary: string, evidence: list, limitations: list}. "
        "Evidence must name tested inputs, methods, logs and results. Separate actual listening or client replay "
        "from static checks. Optional configPatch is restricted to the declared domains. "
        "To import a resource, add its permitted input key to outputs with a file under output/. "
        "Never modify the conductor state or claim a failed stage passed. complete-task validates and applies "
        "the result; run then rebuilds and independently validates the pipeline.\n", encoding="utf-8")
    return task


def create_task(project, role, objective, kind='review'):
    project = Path(project).resolve(strict=True)
    with project_lock(project):
        return _create_task(project, load_config(project), role, objective, kind)


def list_tasks(project):
    project = Path(project).resolve(strict=True)
    return [read_json(p) for p in sorted(owned(project, "tasks").glob("*/task.json"))]


def _find_task(project, task_id):
    if not re.fullmatch(r"(?:" + '|'.join(ROLES) + r")-[a-f0-9]{16}", task_id):
        raise PipelineError("Invalid task ID")
    return owned(project, f"tasks/{task_id}/task.json")


def claim_task(project, task_id, agent):
    project = Path(project).resolve(strict=True)
    with project_lock(project):
        config = load_config(project)
        path = _find_task(project, task_id)
        task = read_json(path)
        if task["inputFingerprint"] != _request_signature(project, config):
            raise PipelineError("Task input is stale; run the project to generate a current task")
        if task["status"] == "claimed" and task.get("agent") == agent:
            return task
        if task["status"] != "pending":
            raise PipelineError("Task is not pending")
        task.update(status="claimed", agent=agent, claimedAt=time.time())
        atomic_json(path, task)
        return task


def complete_task(project, task_id, result):
    project = Path(project).resolve(strict=True)
    with project_lock(project):
        config = load_config(project)
        path = _find_task(project, task_id)
        task = read_json(path)
        result_path = source_path(project, str(result))
        if task["status"] == "completed":
            if (result_path.is_relative_to(path.parent.resolve()) and result_path.is_file()
                    and hash_file(result_path) == task.get("resultSha256")):
                return task
            raise PipelineError("Completed task cannot accept a different result")
        if task["status"] not in ("pending", "claimed"):
            raise PipelineError("Task is already closed")
        if task["inputFingerprint"] != _request_signature(project, config):
            raise PipelineError("Refusing stale task result")
        if not result_path.is_relative_to(path.parent.resolve()) or not result_path.is_file():
            raise PipelineError("Result JSON must be inside the task directory")
        data = read_json(result_path)
        outputs = data.get("outputs")
        required = TASK_KINDS[task['mode']]
        allowed = ROLE_IMPORTS[task["role"]] | required
        if not isinstance(outputs, dict) or not required <= outputs.keys() or not outputs.keys() <= allowed:
            raise PipelineError(f"Task outputs must include {sorted(required)} and only {sorted(allowed)}")
        imported = {}
        for key, value in outputs.items():
            resource = source_path(project, value)
            if not resource.is_relative_to((path.parent / "output").resolve()) or not resource.is_file():
                raise PipelineError("Every resource must remain within this task's output directory")
            if key == "midi":
                from .midi import parse_midi
                parse_midi(resource.read_bytes())
            elif key in {"review", "captions", "adaptationPlan", "soundProfile", "stageModule", "showScore", "proposal"}:
                document = read_json(resource)
                if not isinstance(document, dict):
                    raise PipelineError(f"{key} must be a JSON object")
                if key == "review" and not (isinstance(document.get("summary"), str)
                        and isinstance(document.get("evidence"), list) and isinstance(document.get("limitations"), list)):
                    raise PipelineError("Review requires summary, evidence and limitations")
                contracts = {'soundProfile': 'sound-profile', 'stageModule': 'stage-module', 'showScore': 'show-score',
                             'adaptationPlan': 'adaptation-plan'}
                if key in contracts:
                    from .contracts import validate_contract
                    validate_contract(document, contracts[key])
                if key == 'soundProfile':
                    from .music_tools import validate_sound_profile
                    validate_sound_profile(resource)
                    for slot in document.get('slots', {}).values():
                        if slot.get('sample'):
                            sample = (resource.parent / slot['sample']).resolve()
                            if not sample.is_relative_to((path.parent / 'output').resolve()):
                                raise PipelineError('Task sound samples must remain inside its output directory')
            elif key == "soundPack":
                import zipfile
                with zipfile.ZipFile(resource) as archive:
                    if "pack.mcmeta" not in archive.namelist() or archive.testzip():
                        raise PipelineError("Sound pack requires a valid ZIP with pack.mcmeta at root")
            imported[key] = {"path": resource.relative_to(project).as_posix(), "sha256": hash_file(resource)}
        patch = data.get("configPatch", {})
        if not isinstance(patch, dict) or not patch.keys() <= ROLE_DOMAINS[task["role"]]:
            raise PipelineError("Config patch exceeds specialist's allowed domains")
        def check_patch(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if re.search(r"shell|command|exec|entrypoint", key, re.I):
                        raise PipelineError("Task configuration cannot supply executable commands")
                    check_patch(child)
            elif isinstance(value, list):
                for child in value:
                    check_patch(child)
        check_patch(patch)
        if "runtime" in patch:
            permitted_runtime = {"serverValidation", "timeoutSeconds"}
            if not isinstance(patch["runtime"], dict) or not patch["runtime"].keys() <= permitted_runtime:
                raise PipelineError("Tasks cannot change trusted executables, runtime paths or accept EULA")
        for domain, values in patch.items():
            if not isinstance(values, dict):
                raise PipelineError("Configuration domains must be objects")
            supported = {'music': {}, 'sound': {'profile': str, 'retrigger': bool, 'adapter':str, 'consistency':str},
                         'machine': {'decorate': bool}, 'layout': {'families': list, 'camera': dict}, 'visuals': {'enabled': bool},
                         'validation': {}, 'runtime': {'serverValidation': bool, 'timeoutSeconds': int}}[domain]
            if not values.keys() <= supported.keys():
                raise PipelineError(f'Unsupported configuration keys in {domain}; a code change is needed')
            for key, value in values.items():
                if type(value) is not supported[key]:
                    raise PipelineError(f'Invalid type for {domain}.{key}')
                if key == 'timeoutSeconds' and not 30 <= value <= 1800:
                    raise PipelineError('Task runtime timeout must be 30..1800 seconds')
                if key == 'profile' and (not value or len(value) > 64 or not re.fullmatch(r'[a-z0-9_-]+', value)):
                    raise PipelineError('Invalid sound profile name')
            config[domain] = {**config.get(domain, {}), **values}
        for key in ROLE_IMPORTS[task["role"]] & imported.keys():
            config["inputs"][key] = imported[key]["path"]
        task.update(status="completed", completedAt=time.time(),
                    resultSha256=hash_file(result_path), outputs=imported, appliedConfigPatch=patch,
                    stagePassGranted=False)
        atomic_json(project / "project.json", config)
        atomic_json(path, task)
        return task


def run_pipeline(project, until="release", force=False, overrides=None):
    project = Path(project).resolve(strict=True)
    if until not in STAGES:
        raise PipelineError("Unknown stage")
    overrides = overrides or {}
    with project_lock(project):
        config = load_config(project)
        state_path = owned(project, "state.json")
        state = read_json(state_path) if state_path.exists() else {"schemaVersion": 1, "stages": {}}
        state["status"] = "running"
        if not config["inputs"].get("midi") and not config["inputs"].get("approvedEvents"):
            task = create_music_task(project, config)
            state.update(status="awaiting_agent", task=task["id"])
            atomic_json(state_path, state)
            return state
        outputs, dep_fingerprints, run_log = {}, {}, []
        for stage in STAGES[:STAGES.index(until) + 1]:
            staging = None
            fingerprint = None
            attempts = 0
            try:
                module = None if stage in overrides else importlib.import_module("redstone_music." + stage)
                fingerprint = input_fingerprint(project, config, stage,
                    {key: dep_fingerprints[key] for key in DEPENDENCIES[stage]}, module, overrides.get(stage))
                previous = state["stages"].get(stage, {})
                cached_path = owned(project, previous["artifact"]) if previous.get("artifact") else None
                if (not force and previous.get("status") == "passed" and previous.get("inputFingerprint") == fingerprint
                        and cached_path and artifact_valid(cached_path, previous)):
                    outputs[stage] = str(cached_path)
                    dep_fingerprints[stage] = previous["fingerprint"]
                    run_log.append({"stage": stage, "action": "cached"})
                    continue
                attempts = (previous.get("attempts", 0) if previous.get("status") in ("failed", "running")
                            and previous.get("inputFingerprint") == fingerprint else 0) + 1
                limit = config.get("policy", {}).get("maxAttempts", 2)
                if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                    raise PipelineError("policy.maxAttempts must be a positive integer")
                if not force and attempts > limit:
                    raise PipelineError("Attempt budget exhausted for unchanged input; repair the task or use --force for an explicit retry")
                staging = owned(project, ".staging/" + stage + "-" + uuid.uuid4().hex[:12])
                staging.mkdir(parents=True)
                state["stages"][stage] = {"status": "running", "inputFingerprint": fingerprint,
                                          "attempts": attempts, "startedAt": time.time()}
                atomic_json(state_path, state)
                context = {"project": str(project), "root": str(REPO_ROOT), "config": config,
                           "deps": {key: outputs[key] for key in DEPENDENCIES[stage]}, "out": str(staging)}
                summary = (overrides.get(stage) or module.run)(context)
                if not isinstance(summary, dict):
                    raise PipelineError("Stage must return a JSON object summary")
                digest(summary)  # also checks JSON serializability and nonfinite numbers
                after = input_fingerprint(project, config, stage,
                    {key: dep_fingerprints[key] for key in DEPENDENCIES[stage]}, module, overrides.get(stage))
                if after != fingerprint:
                    raise PipelineError('Stage inputs or tool sources changed during execution; result cannot be certified')
                if stage == 'music' and (staging / 'score.json').is_file():
                    score = read_json(staging / 'score.json')
                    duration = score.get('durationSeconds')
                    if (not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0
                            or duration > config.get('policy', {}).get('maxDurationSeconds', 900)):
                        raise PipelineError('Score duration exceeds the configured production budget')
                    if not isinstance(score.get('notes'), list) or len(score['notes']) > config.get('policy', {}).get('maxNotes', 50000):
                        raise PipelineError('Score note count exceeds the configured production budget')
                if stage == 'sound' and (staging / 'events.json').is_file():
                    events = read_json(staging / 'events.json')
                    if len(events.get('candidates', [])) > config.get('policy', {}).get('maxNotes', 50000) * 4:
                        raise PipelineError('Adapted event count exceeds the configured production budget')
                files = file_map(staging)
                if not files:
                    raise PipelineError("Stage returned no output files")
                artifact_fingerprint = digest({"inputFingerprint": fingerprint, "files": files, "summary": summary})
                manifest = {"schemaVersion": 1, "stage": stage, "inputFingerprint": fingerprint,
                            "fingerprint": artifact_fingerprint, "files": files, "summary": summary}
                atomic_json(staging / "stage_manifest.json", manifest)
                # Keep project-relative paths usable on Windows without requiring
                # system long-path policy changes. The full hash is always verified.
                destination = owned(project, f"artifacts/{stage}/{artifact_fingerprint[:20]}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                record = {"status": "passed", "inputFingerprint": fingerprint, "fingerprint": artifact_fingerprint,
                          "manifestSha256": digest(manifest), "artifact": destination.relative_to(project).as_posix(),
                          "summary": summary, "completedAt": time.time(), "attempts": attempts}
                if destination.exists():
                    existing_manifest = destination / "stage_manifest.json"
                    try:
                        existing_fingerprint = read_json(existing_manifest).get("fingerprint")
                    except (OSError, ValueError):
                        existing_fingerprint = None
                    if existing_fingerprint and existing_fingerprint != artifact_fingerprint:
                        raise PipelineError("Artifact path hash-prefix collision; preserve both versions and use a longer directory prefix")
                    if artifact_valid(destination, record):
                        shutil.rmtree(staging)
                    else:
                        quarantine = owned(project, ".quarantine/" + stage + "-" + uuid.uuid4().hex)
                        quarantine.parent.mkdir(parents=True, exist_ok=True)
                        _rename_artifact(destination, quarantine)
                        _rename_artifact(staging, destination)
                else:
                    _rename_artifact(staging, destination)
                staging = None
                state["stages"][stage] = record
                outputs[stage] = str(destination)
                dep_fingerprints[stage] = artifact_fingerprint
                run_log.append({"stage": stage, "action": "built"})
                atomic_json(state_path, state)
            except Exception as error:
                failure = {"status": "failed", "error": f"{type(error).__name__}: {error}", "failedAt": time.time(),
                           "inputFingerprint": fingerprint, "attempts": attempts}
                if staging and staging.exists():
                    failure["diagnostics"] = staging.relative_to(project).as_posix()
                state["stages"][stage] = failure
                state.update(status="failed", lastRun=run_log)
                atomic_json(state_path, state)
                role = "quality" if stage in ("validate", "release") else stage
                task = _create_task(project, config, role, f"Repair failed {stage} stage: {type(error).__name__}: {error}")
                state["task"] = task["id"]
                failure["repairTask"] = task["id"]
                atomic_json(state_path, state)
                raise PipelineError(f"Stage {stage} failed: {error}") from error
        state.pop("task", None)
        state.update(status="candidate_ready" if until == "release" else "stage_complete",
                     completedThrough=until, lastRun=run_log,
                     artisticApproval="not_inferred_from_technical_checks")
        atomic_json(state_path, state)
        return state


def status(project):
    project = Path(project).resolve(strict=True)
    config = load_config(project)
    state = read_json(owned(project, "state.json"))
    fingerprints, invalid = {}, set()
    for stage in STAGES:
        record = state.get("stages", {}).get(stage, {})
        if record.get("status") == "passed":
            record["artifactIntact"] = artifact_valid(owned(project, record["artifact"]), record)
            try:
                module = importlib.import_module("redstone_music." + stage)
                current = input_fingerprint(project, config, stage,
                    {key: fingerprints.get(key) for key in DEPENDENCIES[stage]}, module)
                record["stale"] = (current != record["inputFingerprint"] or not record["artifactIntact"]
                                   or bool(set(DEPENDENCIES[stage]) & invalid))
            except (OSError, ValueError, ImportError, PipelineError) as error:
                record.update(stale=True, staleReason=str(error))
            fingerprints[stage] = record["fingerprint"]
            if record["stale"]:
                invalid.add(stage)
        else:
            invalid.add(stage)
    return state


def doctor(project=None):
    from .kit import capabilities
    actual = capabilities(project, probe=False)
    result = {"python": sys.version.split()[0], "node": shutil.which("node"),
              "ffmpeg": shutil.which("ffmpeg"), "packageRoot": str(Path(__file__).resolve().parent),
              "modules": {stage: importlib.util.find_spec("redstone_music." + stage) is not None for stage in STAGES}}
    result["dependencies"] = {name: importlib.util.find_spec(name) is not None for name in ("nbtlib", "numpy", "litemapy")}
    result['capabilities'] = actual['capabilities']
    result['toolChecks'] = actual['commands']
    result['scope'] = 'Lightweight local operations; no game, listening or artistic pass inferred'
    result["executableStages"] = {stage: {"moduleAvailable": result["modules"][stage],
        "prerequisitesAvailable": (bool(result["node"]) and result["dependencies"]["nbtlib"])
            if stage in ("machine", "visuals", "validate") else True} for stage in STAGES}
    if project:
        config = load_config(project)
        result["inputs"] = {key: source_path(project, value).is_file() for key, value in config["inputs"].items() if value}
        result["runtime"] = {"serverValidationEnabled": config.get("runtime", {}).get("serverValidation", False)}
    return result


def summarize_run(project, state):
    project = Path(project).resolve()
    stages = state.get('stages', {})
    result = {'project': str(project), 'status': state.get('status'),
              'completedThrough': state.get('completedThrough'), 'stages': state.get('lastRun', [])}
    if state.get('task'):
        result['task'] = state['task']
        result['taskPath'] = str(owned(project, f'tasks/{state["task"]}/TASK.md'))
    if stages.get('release', {}).get('status') == 'passed':
        release = owned(project, stages['release']['artifact'])
        result['releasePath'] = str(release / 'deliverables.zip')
        result['usagePath'] = str(release / 'USAGE.md')
        result['verification'] = stages['release'].get('summary', {}).get('runtime', {})
    result['warnings'] = list(dict.fromkeys(
        str(warning) for stage in ('visuals', 'validate')
        for warning in stages.get(stage, {}).get('summary', {}).get('warnings', [])))
    result['artisticApproval'] = 'not_inferred_from_technical_checks'
    return result
