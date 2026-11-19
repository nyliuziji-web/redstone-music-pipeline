# Selected music-skill integration

Upstream: [owoevan-dev/music-skill](https://github.com/owoevan-dev/music-skill), pinned commit `ba4338a958132ad6e5664fb6a767369dcb51c102`.

This directory contains unmodified MIT `musiclib/voicing.py` and its `harmony.py` dependency, two selected read-only arranging references, the upstream MIT license, and exact file hashes in `provenance.json`. The local composition adapter verifies these hashes before executing the voicing helper. It does not execute upstream installers, invoke cloud services, or install a global Skill.

The helper performs bounded dynamic programming over candidate voicings. It chooses pitches for an explicit chord sequence; it does not write rhythm, infer the true chords from audio, compose the whole piece or approve music. Its dissonance/spacing preferences are optional arranging heuristics. Parallel-motion avoidance remains off by default because it may be intentional in pop or electronic music.

The public interface is `redstone_music.composition_tools.plan_voicings`. Our separate composition IR preserves source MIDI tempo/control events, binds frozen source notes and allows explicit new arrangement tracks and local revisions. The upstream studio is not presented as a lossless arbitrary-MIDI importer.

Excluded: the GPL Surge host, sample-bank binaries, upstream setup/download scripts, and unrelated model/example quality claims. Renderers and SoundFonts are selected separately under their own terms. The bundled 16-bar exercise uses original notes; no upstream demonstration melody is copied.
