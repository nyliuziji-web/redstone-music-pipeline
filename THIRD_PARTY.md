# Third-party components and data

The MIT license covers this project's own Python modules, control templates and Java rendering sources. It does not relicense Minecraft, reference music or any external dependency.

## Runtime dependencies

| Component | Use | Source and upstream license |
|---|---|---|
| nbtlib | Reading and writing Minecraft NBT | [vberlier/nbtlib](https://github.com/vberlier/nbtlib), MIT |
| NumPy | Array support used by nbtlib | [numpy/numpy](https://github.com/numpy/numpy), BSD-3-Clause; distributed wheels may contain additional notices |
| Node.js | Executing the project's data-pack generator | [nodejs/node](https://github.com/nodejs/node), upstream distribution includes its own licenses |
| Fabric API / Loader | Optional compilation and use of the client renderer | [FabricMC](https://github.com/FabricMC), follow each component's upstream license |
| Java / Minecraft | Optional real-server replay and game playback | Supplied separately by the operator under their applicable terms |

These components are not vendored into the source distribution. Python packages are declared in `pyproject.toml`; matching game libraries and a JDK are provided locally. Do not assume the project's MIT license covers redistribution of dependency binaries.

## Music and visual assets

The Nevada production used third-party reference audio, music arrangements, sound-font material, texture packs and shaders. Those private production assets, game runtime files and generated projects are excluded from the public source tree. Historical experience informed the code; it does not grant rights to redistribute a song, its stems, lyrics, sound fonts, textures or shaders.

`examples/demo.mid` is an original synthetic test phrase dedicated under CC0-1.0, matching the generator's declaration. It contains no sampled audio or excerpt from Nevada. See the [CC0 legal code](https://creativecommons.org/publicdomain/zero/1.0/legalcode).

User-supplied MIDI, captions, sound packs and generated delivery bundles remain subject to the user's source rights and any upstream terms. Public source exports and private performance delivery are separate operations; generated deliverables should not be committed automatically.

## Vendored Minecraft skill reference snapshots

`skills/_upstream/minecraft-agent-skills/` contains unmodified text snapshots of four selected skills from [Jahrome907/minecraft-agent-skills](https://github.com/Jahrome907/minecraft-agent-skills), commit `22d61ce6b7a0c5f215008824aa6b94ecc73f2a43`, obtained 2026-11-17: Minecraft modding, resource packs, datapacks and testing. The upstream MIT copyright and permission notice is retained in that directory's `LICENSE`; `provenance.json` records original paths, immutable source URLs and SHA-256 hashes.

These are reference snapshots (`.txt`), not globally installed or automatically invoked skills. Their examples cover broader game versions and their original relative references are resolved against the upstream repository, not this package. The project's own skills choose the 1.21.1 production path and require actual build/runtime validation. No Minecraft assets or third-party model weights are included with these references.

## Integrated professional tooling

Optional dependencies include Mido, music21, librosa, SoundFile, SciPy, Pillow, TinySoundFont, SwiftF0/ONNX Runtime and JSON Schema. They are installed separately under their distribution notices; their source, dependency graph and pinned local environment are recorded through pyproject/profiles. No external SoundFont is included. The `learn` generator's original MIDI and synthesized sounds are CC0-1.0; project code remains MIT.

Selected MIT source and text from [music-skill](https://github.com/owoevan-dev/music-skill) are pinned under `integrations/music-skill/`. See its upstream LICENSE and provenance hashes. Only the selected voicing helper and references are integrated.

Basic Pitch, Beat This!, audio-separator and MuScriptor are optional separate installations. Treat code and checkpoint licenses independently. FluidSynth and GeneralUser GS are user-supplied or acquired separately under their own terms. See the transcription integration and environment guide for tested versions and asset sources.

The original 16-bar composition study and the 20-second timbre study use CC0-1.0 musical material and generated recipes. Public exports include the original practice materials and code. Audition audio, external SoundFonts, downloaded models and real-song test material stay in local project or runtime folders.

The unmodified sparse voxel module from [harrynull/mcbuild](https://github.com/harrynull/mcbuild), commit `34ce86372d4c23f4d83d4e24fc256cb399d6c3e3`, is vendored in `redstone_music/_vendor/mcbuild_voxel.py`. Its MIT license is preserved in `integrations/mcbuild/LICENSE`, with exact source/hash in provenance.json. Hosted agents, NeoForge runtime and Minecraft textures are excluded.

The standard Gradle wrapper uses upstream Gradle's Apache-2.0 license, retained in `client/gradle/LICENSE-Gradle.txt`. The Fabric build downloads its declared dependencies separately. Photon and its dependencies are not bundled; the exact release license and backend comparison remain separate checks.

`examples/night-study/` contains the independent agent's original MIDI and declarative night-study designs, dedicated under CC0-1.0 with no external music or samples. They are candidate educational assets, not a grant of artistic approval.
