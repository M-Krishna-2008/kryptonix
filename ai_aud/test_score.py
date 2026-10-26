import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio_forensics.analyzer import analyze
from audio_forensics.model_aasist import check_models_available

print("Checking model availability:", check_models_available())

real_file = "audio_forensics/tests/samples/real/sample_voice_real.wav"
synthetic_file = "audio_forensics/tests/samples/synthetic/synthetic_speech_sapi.wav"

print("\n================ SCORING REAL SAMPLE ================")
res_real = analyze(real_file)
print("Verdict:", res_real["verdict"])
print("Confidence:", res_real["overall_confidence"])
print("Errors:", res_real.get("errors", []))
print("Clip summary:", res_real["raw_metrics"].get("clip_summary"))
print("Per window logits:", [w["bona_fide_logit"] for w in res_real["raw_metrics"].get("per_window_logits", [])])
for f in res_real["findings"]:
    print(f"  Finding [{f['severity']}]: {f['check']} - {f['description']}")

print("\n================ SCORING SYNTHETIC SAMPLE ================")
res_synth = analyze(synthetic_file)
print("Verdict:", res_synth["verdict"])
print("Confidence:", res_synth["overall_confidence"])
print("Errors:", res_synth.get("errors", []))
print("Clip summary:", res_synth["raw_metrics"].get("clip_summary"))
print("Per window logits:", [w["bona_fide_logit"] for w in res_synth["raw_metrics"].get("per_window_logits", [])])
for f in res_synth["findings"]:
    print(f"  Finding [{f['severity']}]: {f['check']} - {f['description']}")
