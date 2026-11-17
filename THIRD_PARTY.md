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
