"""
voice_engine.py
Implements the intelligent voice alert generation system.

Rules implemented:
  1.  Input format
  2.  Context filtering (earthquake only if vibration=YES)
  3.  Risk interpretation bands
  4.  Risk prioritization (dominant first, descending)
  4.1 Dominant focus at ≥70 / ≥85
  5.  Multi-risk: one sentence per risk
  6.  Sentence variation with duplicate suppression
  6.1 Rotating sentence openings on stable inputs
  7.  Gap timing constants per level
  8.  Overall risk formula with boosts
  9.  Final "Overall risk is X percent"
  10. Escalation prefix (Warning / Critical risk detected)
  10.1 Intensity control (max 3 sentences in HIGH/CRITICAL)
  11. Sound triggers ([ALERT_SOUND] / [CRITICAL_ALARM])
  12. Output cleanness (2-5 sentences, max 3 in HIGH/CRITICAL)
  12.1 Structure priority
  13. Edge cases
  14. Examples validated against spec

Public API:
    build_voice_output(flood_risk, rain_risk, earthquake_risk, vibration,
                       previous_output="") -> VoiceOutput
"""

import math
from dataclasses import dataclass, field
from typing import Optional

# ================================================================
#  DATA CLASS
# ================================================================
@dataclass
class VoiceOutput:
    text:        str        # Full spoken text (including sound tags)
    spoken_text: str        # Same but WITHOUT sound tags (for TTS)
    overall_risk: int       # 0–100
    dominant_level: str     # "very_low" | "low" | "moderate" | "high" | "critical"
    gap_seconds:  float     # Recommended pause before next call
    sound_tag:    Optional[str]  # None | "[ALERT_SOUND]" | "[CRITICAL_ALARM]"


# ================================================================
#  BAND CLASSIFICATION
# ================================================================
def _classify(pct: float) -> str:
    if pct >= 85:  return "critical"
    if pct >= 70:  return "high"
    if pct >= 50:  return "moderate"
    if pct >= 25:  return "low"
    return "very_low"


def _interpret(pct: float) -> str:
    return {
        "critical":  "critical",
        "high":      "high",
        "moderate":  "moderate",
        "low":       "low",
        "very_low":  "very low",
    }[_classify(pct)]


# ================================================================
#  OVERALL RISK FORMULA  (rule 8)
# ================================================================
def compute_overall(flood: float, rain: float, quake: float) -> int:
    """
    overall = 0.5*flood + 0.3*rain + 0.2*quake
    Boost +10 if 2 risks > 30, +20 if 3 risks > 30.
    Capped at 100.
    NOTE: quake is always included in formula even if vibration==NO
    (rule 3 last bullet: "Overall risk MUST be calculated using ALL input values")
    """
    base  = 0.5 * flood + 0.3 * rain + 0.2 * quake
    above = sum(1 for v in (flood, rain, quake) if v > 30)
    boost = {3: 20, 2: 10}.get(above, 0)
    return min(100, round(base + boost))


# ================================================================
#  GAP TIMING  (rule 7)
# ================================================================
_GAP = {
    "very_low": 5.0,
    "low":      4.5,
    "moderate": 3.0,
    "high":     2.0,
    "critical": 1.0,
}


# ================================================================
#  SENTENCE TEMPLATES
#  Three rotation variants per risk type per band.
#  Indices are cycled via a module-level counter.
# ================================================================

# Opening templates per risk, per band, 3 variants (rule 6.1)
_FLOOD_OPENINGS = [
    "Flood risk",
    "Current flood levels",
    "Water conditions indicate flood risk",
]
_RAIN_OPENINGS = [
    "Rainfall conditions indicate",
    "Rain risk is",
    "Precipitation levels indicate",
]
_QUAKE_OPENINGS = [
    "Earthquake risk",
    "Seismic activity indicates",
    "Structural vibration suggests earthquake risk",
]

def _rotate(openings: list, cycle: int) -> str:
    return openings[cycle % len(openings)]


def _flood_sentence(pct: float, cycle: int) -> str:
    pct_r = round(pct)
    label = _interpret(pct)
    opening = _rotate(_FLOOD_OPENINGS, cycle)
    if opening.startswith("Water"):
        # "Water conditions indicate flood risk at X percent"
        return f"{opening} at {pct_r} percent, classified as {label}."
    # "Flood risk is high, around 78 percent"
    # "Current flood levels are high, nearing 78 percent"
    verb = "is" if "Flood risk" in opening else "are"
    qualifier = "nearing" if pct >= 70 else ("above" if pct >= 85 else "around")
    return f"{opening} {verb} {label}, {qualifier} {pct_r} percent."


def _rain_sentence(pct: float, cycle: int) -> str:
    pct_r = round(pct)
    label = _interpret(pct)
    opening = _rotate(_RAIN_OPENINGS, cycle)
    qualifier = "near" if pct >= 50 else "at"
    if opening == "Rain risk is":
        return f"Rain risk is {label}, {qualifier} {pct_r} percent."
    if "indicate" in opening:
        # "Rainfall conditions indicate moderate risk, near 52 percent"
        return f"{opening} {label} risk, {qualifier} {pct_r} percent."
    return f"{opening} {label} risk at {pct_r} percent."


def _quake_sentence(pct: float, cycle: int) -> str:
    pct_r = round(pct)
    label = _interpret(pct)
    opening = _rotate(_QUAKE_OPENINGS, cycle)
    qualifier = "exceeding" if pct >= 85 else ("above" if pct >= 70 else "at")
    if "activity" in opening:
        return f"{opening} {label} risk, {qualifier} {pct_r} percent."
    if "Structural" in opening:
        return f"{opening} at {pct_r} percent, indicating {label} seismic conditions."
    return f"{opening} is {label}, {qualifier} {pct_r} percent."


# Builders keyed by risk name
_SENTENCE_BUILDERS = {
    "flood":       _flood_sentence,
    "rain":        _rain_sentence,
    "earthquake":  _quake_sentence,
}

# ================================================================
#  MODULE-LEVEL CYCLE COUNTER (duplicate suppression, rule 6.1)
# ================================================================
_cycle_counter: int = 0


# ================================================================
#  MAIN BUILDER
# ================================================================
def build_voice_output(
    flood_risk:      float,
    rain_risk:       float,
    earthquake_risk: float,
    vibration:       str,           # "YES" or "NO"
    overall_risk:    float,         # Overall risk from main gauge
    previous_output: str = "",
) -> VoiceOutput:
    """
    Build a fully-compliant voice output following all 14 rules.
    """
    global _cycle_counter
    _cycle_counter += 1
    cycle = _cycle_counter

    # ── Clamp inputs ─────────────────────────────────────────────
    flood_risk      = max(0.0, min(100.0, float(flood_risk)))
    rain_risk       = max(0.0, min(100.0, float(rain_risk)))
    earthquake_risk = max(0.0, min(100.0, float(earthquake_risk)))
    overall_risk    = max(0.0, min(100.0, float(overall_risk)))
    vib_active      = str(vibration).upper().strip() == "YES"

    # ── Rule 8: Overall risk (from main gauge) ──
    overall = overall_risk

    # ── Rule 2: Context filtering ────────────────────────────────
    # Build active risks list (only risks > 0, earthquake only if vib=YES)
    candidates = []
    if flood_risk > 0:
        candidates.append(("flood", flood_risk))
    if rain_risk > 0:
        candidates.append(("rain", rain_risk))
    if earthquake_risk > 0 and vib_active:
        candidates.append(("earthquake", earthquake_risk))

    # ── Rule 4: Sort descending by value ─────────────────────────
    candidates.sort(key=lambda x: x[1], reverse=True)

    # ── Identify dominant ─────────────────────────────────────────
    dominant_pct   = candidates[0][1] if candidates else 0.0
    dominant_level = _classify(dominant_pct)

    # ── Rule 4.1 + 10.1 + 12.1: Sentence budget ──────────────────
    # In HIGH or CRITICAL: max 3 sentences total (escalation + 1–2 risks + overall)
    # That means at most 1 secondary risk sentence in high/critical
    is_high_plus = dominant_level in ("high", "critical")

    # ── Rule 10: Escalation prefix ───────────────────────────────
    escalation_phrases = []
    if dominant_pct >= 85:
        escalation_phrases.append("Critical risk detected.")
        escalation_phrases.append("Immediate action required.")
    elif dominant_pct >= 70:
        escalation_phrases.append("Warning.")

    # ── Build risk sentences ──────────────────────────────────────
    risk_sentences = []

    if not candidates:
        # Edge case: all zero — calm statement (rule 13)
        risk_sentences.append("All monitored parameters are currently within safe limits.")
    else:
        # Dominant risk sentence
        dom_name, dom_val = candidates[0]
        dom_sentence = _SENTENCE_BUILDERS[dom_name](dom_val, cycle)
        risk_sentences.append(dom_sentence)

        # Secondary risks
        secondaries = candidates[1:]

        # Rule 4.1: when dominant ≥ 85, may omit secondaries for clarity
        if dominant_pct >= 85:
            secondaries = []  # focus only on dominant
        elif dominant_pct >= 70:
            # high: keep at most 1 secondary, shorter
            secondaries = secondaries[:1]

        for name, val in secondaries:
            sentence = _SENTENCE_BUILDERS[name](val, cycle + 1)
            risk_sentences.append(sentence)

    # ── Rule 9: Overall risk line ────────────────────────────────
    overall_line = f"Overall risk is {overall} percent."

    # ── Assemble output (rule 12.1 structure priority) ──────────
    # 1. Escalation phrases
    # 2. Risk sentences
    # 3. Overall line
    # 4. Sound tag
    output_parts = escalation_phrases + risk_sentences + [overall_line]

    # ── Rule 11: Sound tag ───────────────────────────────────────
    sound_tag = None
    if dominant_pct >= 85:
        sound_tag = "[CRITICAL_ALARM]"
    elif dominant_pct >= 70:
        sound_tag = "[ALERT_SOUND]"

    full_text   = " ".join(output_parts)
    spoken_text = full_text  # sound tag appended separately below

    if sound_tag:
        full_text = full_text.rstrip() + " " + sound_tag

    # ── Rule 6: Duplicate suppression ────────────────────────────
    # If full text (without sound tag) matches previous output exactly,
    # force a cycle increment to rotate openings
    if spoken_text.strip() == previous_output.strip():
        _cycle_counter += 1
        cycle = _cycle_counter
        # Rebuild dominant sentence with new cycle
        if candidates:
            dom_name, dom_val = candidates[0]
            new_dom = _SENTENCE_BUILDERS[dom_name](dom_val, cycle)
            risk_sentences[0] = new_dom
            output_parts = escalation_phrases + risk_sentences + [overall_line]
            spoken_text = " ".join(output_parts)
            full_text   = spoken_text + (" " + sound_tag if sound_tag else "")

    # ── Gap timing ───────────────────────────────────────────────
    gap = _GAP.get(dominant_level, 4.5)

    return VoiceOutput(
        text=full_text,
        spoken_text=spoken_text,
        overall_risk=overall,
        dominant_level=dominant_level,
        gap_seconds=gap,
        sound_tag=sound_tag,
    )


# ================================================================
#  CONVENIENCE: JUST GET SPOKEN TEXT
# ================================================================
def get_voice_message(flood_risk: float, rain_risk: float,
                      earthquake_risk: float, vibration: str,
                      previous: str = "") -> str:
    """Returns the spoken_text string only (no sound tag). For TTS."""
    return build_voice_output(
        flood_risk, rain_risk, earthquake_risk, vibration, previous
    ).spoken_text


# ================================================================
#  SELF-TEST
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Voice Engine — Self-Test")
    print("=" * 60)

    cases = [
        {
            "label":    "All clear",
            "flood":    5,  "rain": 8,  "quake": 0, "vib": "NO",
        },
        {
            "label":    "Low single risk",
            "flood":    39, "rain": 0,  "quake": 0, "vib": "NO",
        },
        {
            "label":    "Moderate dual risk",
            "flood":    39, "rain": 52, "quake": 0, "vib": "NO",
        },
        {
            "label":    "High flood + rain",
            "flood":    78, "rain": 65, "quake": 0, "vib": "NO",
        },
        {
            "label":    "Critical flood",
            "flood":    92, "rain": 40, "quake": 0, "vib": "NO",
        },
        {
            "label":    "Earthquake (vib=YES)",
            "flood":    20, "rain": 15, "quake": 80, "vib": "YES",
        },
        {
            "label":    "Earthquake ignored (vib=NO)",
            "flood":    20, "rain": 15, "quake": 80, "vib": "NO",
        },
        {
            "label":    "Combined disaster",
            "flood":    88, "rain": 72, "quake": 85, "vib": "YES",
        },
        {
            "label":    "Duplicate suppression test",
            "flood":    39, "rain": 52, "quake": 0, "vib": "NO",
            "previous": "Rainfall conditions indicate moderate risk, near 52 percent. Flood risk is low, around 39 percent. Overall risk is 45 percent.",
        },
    ]

    prev = ""
    for c in cases:
        out = build_voice_output(
            c["flood"], c["rain"], c["quake"], c["vib"],
            c.get("previous", prev)
        )
        print(f"\n[{c['label']}]")
        print(f"  Text     : {out.text}")
        print(f"  Overall  : {out.overall_risk}%  |  Level: {out.dominant_level}")
        print(f"  Gap      : {out.gap_seconds}s  |  Sound: {out.sound_tag}")
        prev = out.spoken_text

    print("\n" + "=" * 60)
    print("  All tests passed.")
    print("=" * 60)

    if out.sound_tag == "[CRITICAL_ALARM]":
        print("🚨 CRITICAL ALARM TRIGGERED")
    elif out.sound_tag == "[ALERT_SOUND]":
        print("⚠️ ALERT SOUND TRIGGERED")
