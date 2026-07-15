from __future__ import annotations


def test_downsampling_preserves_local_extremes_gaps_endpoints_and_reference_crossings() -> None:
    from market_evidence.downsample import downsample_points

    points = [
        {"date": f"2026-{index // 28 + 1:02d}-{index % 28 + 1:02d}", "value": 40.0, "missing_reason": None}
        for index in range(280)
    ]
    points[73]["value"] = 49.0
    points[141]["value"] = 31.0
    points[190]["value"] = None
    points[190]["missing_reason"] = "gap"
    points[230]["value"] = 85.0

    sampled = downsample_points(points, max_points=40)
    sampled_values = {point["value"] for point in sampled}

    assert len(sampled) <= 40
    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]
    assert 49.0 in sampled_values
    assert 31.0 in sampled_values
    assert any(point["missing_reason"] == "gap" for point in sampled)
    assert 85.0 in sampled_values
