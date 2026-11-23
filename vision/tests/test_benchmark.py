import json
from benchmarks.benchmark import evaluate


def test_benchmark_unmeasured_without_real_clips(tmp_path):
    result = evaluate(str(tmp_path / "missing-ground.csv"), str(tmp_path / "missing-predictions.csv"))

    assert result["status"] == "unmeasured"
    assert result["combined"]["frames"] == 0
    assert "real clips" in result["reason"]
