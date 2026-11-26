"""List trigger differences between two production snapshots without using MIDI note IDs."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


MUSICAL_FIELDS = ("family", "kind", "mappedMidi", "instrument", "note", "baseBlock", "slot", "gainProxy")


def load_snapshot(path):
    raw = path.read_bytes()
    document = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError("Expected an events.json or expected_events.json object")
    placed = "candidates" not in document
    rows = document.get("notes" if placed else "candidates")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Snapshot has no events to compare")
    excerpt = document.get("info", {}).get("excerpt", {}) if placed else {}
    offset = document.get("sourceOffsetGT", excerpt.get("startGT", 0))
    length = document.get("musicGT", excerpt.get("musicGT"))
    fields = ("q", *MUSICAL_FIELDS, *(("x", "y", "z") if placed else ()))
    required = set(fields) - {"q", "slot", "gainProxy"}
    counts = Counter()
    peaks = Counter()
    for row in rows:
        if not isinstance(row, dict) or not required <= row.keys():
            raise ValueError("Input has incomplete trigger fields. Use the actual stage event file.")
        tick = row.get("q")
        if tick is None:
            if type(row.get("gt")) is not int or type(offset) is not int:
                raise ValueError("Input has no usable local game tick")
            tick = row["gt"] - offset
        if type(tick) is not int or tick < 0:
            raise ValueError("Local game tick must be a nonnegative integer")
        counts[(tick, *(row.get(key) for key in fields[1:]))] += 1
        peaks[tick] += 1
    return fields, (offset, length), counts, max(peaks.values()), hashlib.sha256(raw).hexdigest()


def describe(changes, fields):
    by_role = Counter()
    rows = []
    for key, count in sorted(changes.items(), key=lambda item: (item[0][0], repr(item[0]))):
        row = dict(zip(fields, key))
        by_role[row["family"]] += count
        rows.append({**row, "count": count})
    return {"total": changes.total(), "byRole": dict(sorted(by_role.items())), "events": rows}


def compare(baseline, candidate):
    fields, a_time, a, a_peak, a_sha = load_snapshot(baseline)
    b_fields, b_time, b, b_peak, b_sha = load_snapshot(candidate)
    if fields != b_fields:
        raise ValueError("Compare two sound-stage snapshots or two machine-stage snapshots")
    if a_time != b_time:
        raise ValueError(f"Different project time ranges {a_time} and {b_time}. Align the same excerpt first.")
    return {
        "timeRange": {"sourceOffsetGT": a_time[0], "musicGT": a_time[1]},
        "baselineSha256": a_sha,
        "candidateSha256": b_sha,
        "comparedFields": list(fields),
        "peakStartsPerTick": {"baseline": a_peak, "candidate": b_peak},
        "same": (a & b).total(),
        "missingFromCandidate": describe(a - b, fields),
        "newInCandidate": describe(b - a, fields),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        result = compare(args.baseline, args.candidate)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
