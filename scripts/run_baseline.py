"""Baseline real run over the evaluation set (task T3.6, Checkpoint 2) and speed (T1.8).

Runs Grounding DINO + SAM 2 once per image of data/manifests/eval_manifest_v2.json, then
replays only the spray gate at several confidence settings, so every setting is judged on the
same detections. For each setting it measures, against the official box labels:

    crop_sprayed_pct   crop plant pixels inside the spray footprint / all crop plant pixels
    weed_recall_pct    weed plant pixels inside the spray footprint / all weed plant pixels
    savings_pct        image area not sprayed
    plant counts       crop plants touched, weed plants at least half covered

Settings: "every_mask" sprays every SAM 2 mask (no gate at all); "gate_0.35" keeps the label
policy but no extra confidence limit (the detector already drops boxes below 0.35);
"gate_0.50" and "gate_0.70" (the deployed setting) add a confidence limit. System 2 is not
called here; escalation is measured separately (T1.7).

Usage:
    python scripts/run_baseline.py                       # real models, all 38 images
    python scripts/run_baseline.py --limit 3 --name try  # quick check
    python scripts/run_baseline.py --mock                # plumbing check without weights
Output: data/outputs/baseline/<name>/ with results.json, summary.md and one figure per image.
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.crop_protection import ground_truth_masks, spray_metrics, vegetation_mask  # noqa: E402
from src.evaluation.iou_dice import spray_footprint  # noqa: E402
from src.workflow import VisionWorkflowRunner, create_initial_state  # noqa: E402

CROP_NAMES = {"sugarbeet": "sugar beet", "cotton": "cotton"}
GATE_SETTINGS = [0.35, 0.50, 0.70]
DEPLOYED = "gate_0.70"
AGENT = "gate_0.70+agent"


def timed(fn: Callable, bucket: List[float]) -> Callable:
    """Wrap fn so each call's wall time (after the GPU finishes) is appended to bucket."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        out = fn(*args, **kwargs)
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()
        except ImportError:
            pass
        bucket.append(time.perf_counter() - start)
        return out

    return wrapper


def environment(runner: VisionWorkflowRunner, mock: bool) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "MOCK" if mock else "REAL",
        "detector": runner.detector.model_id,
        "segmenter": runner.segmenter.model_id,
        "python": platform.python_version(),
    }
    try:
        info["git_commit"] = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        ).stdout.strip()
    except OSError:
        pass
    try:
        import torch

        info["torch"] = torch.__version__
        info["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except ImportError:
        info["device"] = "cpu (no torch)"
    return info


def spray_masks(
    runner: VisionWorkflowRunner,
    state: Dict[str, Any],
    buffer: int,
    agent: Any = None,
    reviews: Any = None,
    exclusion: bool = False,
) -> Dict[str, np.ndarray]:
    """Spray footprint of every setting, replaying the gate on the same detections."""
    h, w = state["image"].size[1], state["image"].size[0]
    every = np.zeros((h, w), dtype=bool)
    for m in state.get("masks", []):
        every |= np.asarray(m["mask_array"], dtype=bool)
    footprints = {"every_mask": spray_footprint(every, buffer)}
    deployed = runner.min_confidence
    for limit in GATE_SETTINGS:
        # Evaluation only: the constructor never allows a limit below 0.70.
        runner.min_confidence = limit
        payload = runner.spray_map_node(state)["artifacts"]["spray_map"].payload
        footprints[f"gate_{limit:.2f}"] = spray_footprint(payload["composite_mask"], buffer)
    if exclusion:
        # T1.6: the same gates with crop-labelled pixels removed from the weed masks.
        runner.crop_exclusion = True
        for limit in (0.35, 0.50):
            runner.min_confidence = limit
            payload = runner.spray_map_node(state)["artifacts"]["spray_map"].payload
            footprints[f"gate_{limit:.2f}+exclusion"] = spray_footprint(
                payload["composite_mask"], buffer
            )
        runner.crop_exclusion = False
    runner.min_confidence = deployed
    if agent is not None:
        # The deployed gate plus the escalation agent reviewing what it withheld (T1.7, RQ2).
        runner.escalation_agent = agent
        out = runner.spray_map_node(state)
        runner.escalation_agent = None
        footprints[AGENT] = spray_footprint(
            out["artifacts"]["spray_map"].payload["composite_mask"], buffer
        )
        if reviews is not None:
            reviews.extend(out["spray_map"]["escalation"])
    return footprints


def save_figure(
    image: Image.Image,
    item: Dict[str, Any],
    state: Dict[str, Any],
    crop_px: np.ndarray,
    weed_px: np.ndarray,
    footprints: Dict[str, np.ndarray],
    metrics: Dict[str, Dict[str, Any]],
    path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt

    scale = min(1.0, 900 / max(image.size))
    small = image.resize((round(image.width * scale), round(image.height * scale)))
    rgb = np.asarray(small).astype(float)

    def shrink(mask: np.ndarray) -> np.ndarray:
        return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize(small.size)) > 127

    fig, axes = plt.subplots(1, 4, figsize=(22, 6))
    axes[0].imshow(small)
    for ann in item["annotations"]:
        x1, y1, x2, y2 = (v * scale for v in ann["box"])
        colour = "lime" if ann["category"] == "crop" else "red"
        axes[0].add_patch(
            patches.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, edgecolor=colour, lw=2)
        )
    axes[0].set_title("1. Official labels (green crop, red weed)")

    axes[1].imshow(small)
    for b in state.get("boxes", []):
        x1, y1, x2, y2 = (b[k] * scale for k in ("x1", "y1", "x2", "y2"))
        axes[1].add_patch(
            patches.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, edgecolor="yellow", lw=2)
        )
        axes[1].text(
            x1,
            max(0, y1 - 4),
            f"{b['label']} {b['score']:.2f}",
            color="black",
            fontsize=8,
            bbox=dict(facecolor="yellow", alpha=0.8, pad=1, edgecolor="none"),
        )
    axes[1].set_title(f"2. Grounding DINO ({len(state.get('boxes', []))} boxes)")

    last = AGENT if AGENT in footprints else DEPLOYED
    for ax, key in ((axes[2], "gate_0.35"), (axes[3], last)):
        sprayed = shrink(footprints[key])
        overlay = rgb.copy()
        overlay[sprayed] = 0.5 * overlay[sprayed] + 0.5 * np.array([255, 220, 0])
        overlay[sprayed & shrink(crop_px)] = [220, 30, 30]
        overlay[sprayed & shrink(weed_px)] = [30, 200, 60]
        ax.imshow(overlay.astype(np.uint8))
        m = metrics[key]
        ax.set_title(
            f"{3 if key == 'gate_0.35' else 4}. Spray, {key}\n"
            f"crop sprayed {m['crop_sprayed_pct']}% · weed recall {m['weed_recall_pct']}%"
        )
    for ax in axes:
        ax.axis("off")
    fig.suptitle(
        f"{item['image_id']}   red = crop sprayed, green = weed sprayed, yellow = other sprayed area",
        y=0.99,
    )
    plt.tight_layout(rect=(0, 0, 1, 0.93))
    plt.savefig(path, dpi=80)
    plt.close(fig)


def pooled(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    """Pixel-pooled and per-plant totals for one setting over the given images."""
    m = [r["metrics"][key] for r in rows]
    crop = sum(x["crop_pixels"] for x in m)
    weed = sum(x["weed_pixels"] for x in m)
    return {
        "images": len(rows),
        "crop_sprayed_pct": round(100 * sum(x["crop_pixels_sprayed"] for x in m) / crop, 2)
        if crop
        else None,
        "weed_recall_pct": round(100 * sum(x["weed_pixels_sprayed"] for x in m) / weed, 2)
        if weed
        else None,
        "savings_pct_mean": round(statistics.mean(x["savings_pct"] for x in m), 2),
        "crop_plants_damaged": f"{sum(x['crop_plants_damaged'] for x in m)}/{sum(x['crop_plants'] for x in m)}",
        "weed_plants_hit": f"{sum(x['weed_plants_hit'] for x in m)}/{sum(x['weed_plants'] for x in m)}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--manifest", default=str(PROJECT_ROOT / "data/manifests/eval_manifest_v2.json")
    )
    parser.add_argument("--name", default=datetime.now().strftime("%Y%m%d_%H%M"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--buffer", type=int, default=10, help="spray buffer in pixels")
    parser.add_argument(
        "--prompt", default="weed . {crop} plant .", help="{crop} is replaced per image"
    )
    parser.add_argument("--mock", action="store_true")
    parser.add_argument(
        "--agent", action="store_true", help="also score the deployed gate + escalation agent"
    )
    parser.add_argument(
        "--agent-plants", type=int, default=3, help="plants the agent reviews per photo"
    )
    parser.add_argument(
        "--exclusion", action="store_true", help="also score gates with crop exclusion (T1.6)"
    )
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    items = manifest["items"][: args.limit]
    out_dir = PROJECT_ROOT / "data/outputs/baseline" / args.name
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)

    load_start = time.perf_counter()
    runner = VisionWorkflowRunner(mock_mode=args.mock, buffer_pixels=args.buffer)
    runner.system2 = None  # vision only; escalation is measured with --agent
    agent = None
    if args.agent:
        try:
            from dotenv import load_dotenv

            load_dotenv(PROJECT_ROOT / ".env")
        except ImportError:
            pass
        from src.agents.escalation_agent import EscalationAgent

        agent = EscalationAgent(max_plants=args.agent_plants)
    load_seconds = time.perf_counter() - load_start
    detect_times: List[float] = []
    segment_times: List[float] = []
    runner.detector.detect_to_state_boxes = timed(
        runner.detector.detect_to_state_boxes, detect_times
    )
    runner.segmenter.segment_to_state_masks = timed(
        runner.segmenter.segment_to_state_masks, segment_times
    )

    rows = []
    for index, item in enumerate(items, 1):
        image = Image.open(PROJECT_ROOT / item["image_path"]).convert("RGB")
        crop_name = CROP_NAMES[item["crop_type"]]
        state = create_initial_state(image, text_prompt=args.prompt.format(crop=crop_name))
        state["field_metadata"] = {"crop": crop_name}
        start = time.perf_counter()
        state = runner.run(state)
        seconds = time.perf_counter() - start

        vegetation = vegetation_mask(np.asarray(image))
        crop_px, weed_px, crop_objects, weed_objects = ground_truth_masks(
            item["annotations"], vegetation
        )
        reviews: List[Dict[str, Any]] = []
        footprints = spray_masks(runner, state, args.buffer, agent, reviews, args.exclusion)
        metrics = {
            key: spray_metrics(sprayed, crop_px, weed_px, crop_objects, weed_objects)
            for key, sprayed in footprints.items()
        }
        rows.append(
            {
                "image_id": item["image_id"],
                "crop_type": item["crop_type"],
                "size": list(image.size),
                "seconds": round(seconds, 2),
                "detect_seconds": round(detect_times[-1], 2) if detect_times else None,
                "segment_seconds": round(segment_times[-1], 2)
                if segment_times and state.get("boxes")
                else None,
                "refinements": state.get("refinement_count", 0),
                "boxes": [
                    {"label": b["label"], "score": round(b["score"], 3)}
                    for b in state.get("boxes", [])
                ],
                "metrics": metrics,
                "agent_reviews": reviews,
            }
        )
        save_figure(
            image,
            item,
            state,
            crop_px,
            weed_px,
            footprints,
            metrics,
            out_dir / "figures" / f"{Path(item['image_id']).stem}.png",
        )
        d = metrics[AGENT] if agent else metrics[DEPLOYED]
        e = metrics["gate_0.35"]
        print(
            f"[{index:2d}/{len(items)}] {item['image_id']:34s} {seconds:5.1f}s  boxes={len(state.get('boxes', []))}  "
            f"gate0.35: crop {e['crop_sprayed_pct']}% weed {e['weed_recall_pct']}%  |  "
            f"{'agent' if agent else 'gate0.70'}: crop {d['crop_sprayed_pct']}% weed {d['weed_recall_pct']}%"
            + (f"  verdicts={[r['verdict'] for r in reviews]}" if agent else ""),
            flush=True,
        )

    keys = (
        ["every_mask"]
        + [f"gate_{t:.2f}" for t in GATE_SETTINGS]
        + (["gate_0.35+exclusion", "gate_0.50+exclusion"] if args.exclusion else [])
        + ([AGENT] if agent else [])
    )
    beet = [r for r in rows if r["crop_type"] == "sugarbeet"]
    cotton = [r for r in rows if r["crop_type"] == "cotton"]
    warm = [r["seconds"] for r in rows[1:]] or [r["seconds"] for r in rows]
    summary = {
        "sugarbeet": {k: pooled(beet, k) for k in keys} if beet else {},
        "cotton": {k: pooled(cotton, k) for k in keys} if cotton else {},
        "speed": {
            "model_load_seconds": round(load_seconds, 1),
            "seconds_per_image_median_after_first": round(statistics.median(warm), 2),
            "seconds_per_image_mean_after_first": round(statistics.mean(warm), 2),
            "detect_seconds_median": round(statistics.median(detect_times[1:] or detect_times), 2)
            if detect_times
            else None,
            "segment_seconds_median": round(
                statistics.median(segment_times[1:] or segment_times), 2
            )
            if segment_times
            else None,
            "first_image_seconds": rows[0]["seconds"] if rows else None,
        },
    }
    run_info = {
        "environment": environment(runner, args.mock),
        "manifest": {"path": args.manifest, "version": manifest.get("manifest_version")},
        "settings": {
            "prompt": args.prompt,
            "buffer_pixels": args.buffer,
            "gates": keys,
            "detector_box_threshold": runner.detector.box_threshold,
            "system2": "not called",
        },
    }
    (out_dir / "results.json").write_text(
        json.dumps({**run_info, "summary": summary, "images": rows}, indent=2)
    )

    lines = [
        f"# Baseline run `{args.name}` ({run_info['environment']['mode']})",
        "",
        "```",
        json.dumps(run_info, indent=2),
        "```",
        "",
    ]
    for crop_type, table in (
        ("Sugar beet (crop + weed labels)", summary["sugarbeet"]),
        ("Cotton (weed labels only)", summary["cotton"]),
    ):
        if not table:
            continue
        lines += [
            f"## {crop_type}",
            "",
            "| setting | crop sprayed % | weed recall % | savings % | crop plants touched | weeds hit |",
            "|---|---|---|---|---|---|",
        ]
        for k, v in table.items():
            lines.append(
                f"| {k} | {v['crop_sprayed_pct']} | {v['weed_recall_pct']} | {v['savings_pct_mean']} | "
                f"{v['crop_plants_damaged']} | {v['weed_plants_hit']} |"
            )
        lines.append("")
    lines += ["## Speed", "", "```", json.dumps(summary["speed"], indent=2), "```"]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines[len(lines) - 25 :]) if len(lines) > 25 else "\n".join(lines))
    print(f"\nWritten to {out_dir.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
