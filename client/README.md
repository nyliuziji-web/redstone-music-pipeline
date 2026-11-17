# Portable Fabric client source

Target: Minecraft Java 1.21.1, JDK21, Fabric Loader0.18.2, Fabric API0.116.4+1.21.1. Uses pinned Yarn names and Loom1.9.2; build with Gradle8.12.1 or the included wrapper.

```shell
./gradlew --no-daemon -Dfabric.loom.ci=true build
```

The remapped runtime JAR is under `build/libs/`. `build-client` can run this build with an explicit JDK and capture a build report. Loom's CI flag skips downloading/remapping dependency source JARs that are useful to an IDE but unnecessary for a batch build. Compilation is not visual or listening approval.

The client reads `config/redstone_music/show_score.json` first, otherwise the same file embedded under `assets/redstone_music/`. `compile-show` creates that schema. `/rmp reload` reloads a changed local score. `/rmp status` prints a JSON diagnostic with loaded status, current music GT, run, active particles, emitted particles and peak particles. `RMP_SHOW_*` lines also appear in the ordinary game log. These counters establish synchronization/cleanup behavior, not aesthetic approval. The pipeline can embed a per-project score into a supplied `runtime.clientJar`.

Its clock is the physical machine's integrated-server command storage `<namespace>:fx`: playing=2, enabled=1, q, run and sample. It does not play any music or infer timing from an external song. The current reference backend supports deterministic node/ring/helix/bezier point geometry and centered fixed-screen caption cues. Owned particles are cleared on stop, world unload and replay. Remote multiplayer synchronization is not implemented.

This is a restrained reference backend for same-scene comparisons, not a claim to equal ColorBlock/Photon or reproduce a bespoke show. Real gameplay, final shaders, recording load and user review remain necessary.
