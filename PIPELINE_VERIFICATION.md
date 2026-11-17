# v0.1 verification — 2026-11-17

The pipeline was exercised as executable software, with separate claims for each level of verification.

- Unit/integration suite: **47 tests**, all successful in the development workspace. In the exported public source checkout, all public tests passed and the private Nevada-data regression was skipped (47 discovered, 1 skipped).
- Independent public checkout: ran the original eight-second demo through all six stages to a delivery ZIP, using no Nevada source data or private game runtime. World and Litematic bytes were independently decoded and checked. Visual assets were generated; the checkout correctly reported that no client compilation environment was supplied.
- Development machine: compiled the Fabric visual/caption client successfully against the local Java 1.21.1 environment.
- Actual Minecraft Java 1.21.1 server: built the test observer from the included Java sources, then ran the original demo. All 10 physical events matched pitch, timbre, exact game tick and camera target. Mid-song stop produced no later events; a subsequent full replay matched again. This was a real isolated server at its normal tick rate, not offline audio simulation.
- Nevada regression: the generic compiler preserved all **6,604** approved events' timing, pitch, timbre and coordinates. Its newly generated 306,411-block candidate passed independent Anvil/Litematica export checks. This is a compiler regression, not a replacement for the separately produced final Nevada show.
- Release checks bind world, schematic, data pack, resources and optional client files to their validated hashes. A change after validation is rejected.

Newly generated client rendering, subjective listening, screen recording and publication were **not** performed for this software release. A compiled mod is not a client-rendering test. The generic visual template is a candidate generator, not a claim to reproduce all bespoke artistic decisions from Nevada.

Public source contains no reference recordings, commercial song MIDI, sample packs, textures/shaders, Minecraft binaries, personal profiles or local runtime configuration. The original synthetic demo composition is CC0; source code is MIT.

Source repository publication is tracked separately from the technical tests above. Publishing source code does not establish video recording, artistic approval or game-client verification.
