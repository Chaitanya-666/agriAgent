# Baseline run `exclusion_v2_20261018` (REAL)

```
{
  "environment": {
    "date_utc": "2026-10-18T08:08:01Z",
    "mode": "REAL",
    "detector": "IDEA-Research/grounding-dino-tiny",
    "segmenter": "facebook/sam2-hiera-tiny",
    "python": "3.11.15",
    "git_commit": "f721017",
    "torch": "2.11.0+cu128",
    "device": "NVIDIA GeForce RTX 5050 Laptop GPU"
  },
  "manifest": {
    "path": "/mnt/Windows_D/College-work/finalYearProjectAgriAgent/data/manifests/eval_manifest_v2.json",
    "version": "2.0.0"
  },
  "settings": {
    "prompt": "weed . {crop} plant .",
    "buffer_pixels": 10,
    "gates": [
      "every_mask",
      "gate_0.35",
      "gate_0.50",
      "gate_0.70",
      "gate_0.35+exclusion",
      "gate_0.50+exclusion"
    ],
    "detector_box_threshold": 0.35,
    "system2": "not called"
  }
}
```

## Sugar beet (crop + weed labels)

| setting | crop sprayed % | weed recall % | savings % | crop plants touched | weeds hit |
|---|---|---|---|---|---|
| every_mask | 93.92 | 97.58 | 39.33 | 87/93 | 265/282 |
| gate_0.35 | 70.79 | 9.03 | 93.0 | 45/93 | 7/282 |
| gate_0.50 | 20.52 | 6.77 | 97.95 | 8/93 | 1/282 |
| gate_0.70 | 0.0 | 0.0 | 100.0 | 0/93 | 0/282 |
| gate_0.35+exclusion | 50.11 | 9.03 | 94.9 | 38/93 | 7/282 |
| gate_0.50+exclusion | 5.25 | 6.77 | 99.32 | 2/93 | 1/282 |

## Cotton (weed labels only)

| setting | crop sprayed % | weed recall % | savings % | crop plants touched | weeds hit |
|---|---|---|---|---|---|
| every_mask | None | 75.81 | 84.17 | 0/0 | 13/19 |
| gate_0.35 | None | 0.0 | 100.0 | 0/0 | 0/19 |
| gate_0.50 | None | 0.0 | 100.0 | 0/0 | 0/19 |
| gate_0.70 | None | 0.0 | 100.0 | 0/0 | 0/19 |
| gate_0.35+exclusion | None | 0.0 | 100.0 | 0/0 | 0/19 |
| gate_0.50+exclusion | None | 0.0 | 100.0 | 0/0 | 0/19 |

## Speed

```
{
  "model_load_seconds": 3.5,
  "seconds_per_image_median_after_first": 0.57,
  "seconds_per_image_mean_after_first": 0.56,
  "detect_seconds_median": 0.2,
  "segment_seconds_median": 0.27,
  "first_image_seconds": 2.27
}
```
