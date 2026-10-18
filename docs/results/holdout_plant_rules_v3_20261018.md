# Baseline run `holdout_plant_rules_v3` (REAL)

```
{
  "environment": {
    "date_utc": "2026-10-18T08:57:05Z",
    "mode": "REAL",
    "detector": "IDEA-Research/grounding-dino-tiny",
    "segmenter": "facebook/sam2-hiera-tiny",
    "python": "3.11.15",
    "git_commit": "6517cc6",
    "torch": "2.11.0+cu128",
    "device": "NVIDIA GeForce RTX 5050 Laptop GPU"
  },
  "manifest": {
    "path": "data/manifests/eval_manifest_v2_holdout.json",
    "version": "2.0.0-holdout"
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
      "gate_0.70",
      "gate_0.35+exclusion",
      "gate_0.50+exclusion"
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
| every_mask | 94.43 | 93.2 | 60.23 | 334/363 | 204/215 |
| every_plant_mask | 92.48 | 1.78 | 79.66 | 295/363 | 3/215 |
| plant_rules | 8.84 | 77.93 | 94.96 | 104/363 | 177/215 |
| plant_rules+crop_guard | 8.82 | 77.86 | 94.96 | 102/363 | 177/215 |
| gate_0.35 | 65.45 | 1.78 | 85.03 | 242/363 | 3/215 |
| gate_0.50 | 22.45 | 0.0 | 95.54 | 49/363 | 0/215 |
| gate_0.70 | 0.0 | 0.0 | 100.0 | 0/363 | 0/215 |
| gate_0.35+exclusion | 41.92 | 1.78 | 89.6 | 216/363 | 3/215 |
| gate_0.50+exclusion | 5.51 | 0.0 | 98.77 | 24/363 | 0/215 |

## Speed

```
{
  "model_load_seconds": 3.8,
  "seconds_per_image_median_after_first": 0.58,
  "seconds_per_image_mean_after_first": 0.57,
  "detect_seconds_median": 0.21,
  "segment_seconds_median": 0.37,
  "first_image_seconds": 1.47
}
```
