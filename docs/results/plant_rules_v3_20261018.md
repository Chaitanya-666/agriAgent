# Baseline run `plant_rules_v3` (REAL)

```
{
  "environment": {
    "date_utc": "2026-10-18T08:54:43Z",
    "mode": "REAL",
    "detector": "IDEA-Research/grounding-dino-tiny",
    "segmenter": "facebook/sam2-hiera-tiny",
    "python": "3.11.15",
    "git_commit": "6517cc6",
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
      "every_plant_mask",
      "plant_rules",
      "plant_rules+crop_guard",
      "gate_0.35",
      "gate_0.50",
      "gate_0.70"
    ],
    "detector_box_threshold": 0.35,
    "detector_tiles": 1,
    "system2": "not called"
  }
}
```

## Sugar beet (crop + weed labels)

| setting | crop sprayed % | weed recall % | savings % | crop plants touched | weeds hit |
|---|---|---|---|---|---|
| every_mask | 93.92 | 97.58 | 39.33 | 87/93 | 265/282 |
| every_plant_mask | 84.67 | 9.13 | 91.56 | 53/93 | 8/282 |
| plant_rules | 4.55 | 71.47 | 90.47 | 21/93 | 219/282 |
| plant_rules+crop_guard | 4.53 | 71.19 | 90.48 | 21/93 | 219/282 |
| gate_0.35 | 70.79 | 9.03 | 93.0 | 45/93 | 7/282 |
| gate_0.50 | 20.52 | 6.77 | 97.95 | 8/93 | 1/282 |
| gate_0.70 | 0.0 | 0.0 | 100.0 | 0/93 | 0/282 |

## Cotton (weed labels only)

| setting | crop sprayed % | weed recall % | savings % | crop plants touched | weeds hit |
|---|---|---|---|---|---|
| every_mask | None | 75.81 | 84.17 | 0/0 | 13/19 |
| every_plant_mask | None | 75.81 | 84.17 | 0/0 | 13/19 |
| plant_rules | None | 10.4 | 97.78 | 0/0 | 7/19 |
| plant_rules+crop_guard | None | 10.4 | 97.78 | 0/0 | 7/19 |
| gate_0.35 | None | 0.0 | 100.0 | 0/0 | 0/19 |
| gate_0.50 | None | 0.0 | 100.0 | 0/0 | 0/19 |
| gate_0.70 | None | 0.0 | 100.0 | 0/0 | 0/19 |

## Speed

```
{
  "model_load_seconds": 3.9,
  "seconds_per_image_median_after_first": 0.56,
  "seconds_per_image_mean_after_first": 0.56,
  "detect_seconds_median": 0.21,
  "segment_seconds_median": 0.28,
  "first_image_seconds": 1.45
}
```
