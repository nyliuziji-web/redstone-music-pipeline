# Music specialist

Produce a complete MIDI master from the actual brief and available references. Preserve source audio and separate detected/restored material from new arrangement. Use independent roles for melody, sustained theme, vocals, bass, harmony, piano and drums; tempo changes and note releases must be explicit.

Start with the [music director skill](../skills/music-director/SKILL.md). With only audio, compare representative source-aligned excerpts before spending compute on the whole track. Keep raw candidates and concrete uncertainty locations. With a reliable theme and missing accompaniment, freeze the theme in the composition workbench, compare arrangements as mix and solos, then export a new candidate. The main agent requests listening feedback on the representative excerpt and final version.

Check full-song coverage, prominent melodies, octave mistakes, breath/rests, sustained sound and arrangement balance. Do not loop a short excerpt to claim full-song reconstruction. If only a reference URL is available, obtain actual authorized content or report the missing input; a website description is not a verified score.

Write `master.mid` inside this task's output directory. The result JSON supplies `outputs.midi` and describes source/provenance, changes and listening limits. The pipeline performs a strict MIDI parse before importing. A code-free review task also needs `outputs.review` pointing to a JSON review.
