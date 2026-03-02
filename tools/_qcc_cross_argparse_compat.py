# NOTE: This file is a compatibility shim patch.
# It only adjusts CLI argument parsing so the workflow can pass --dataset or --dataset-path.

from __future__ import annotations

import argparse

def _patch_argparse(parser: argparse.ArgumentParser) -> None:
    # Replace any required --dataset declaration with a dual-flag alias.
    # We do this safely by adding an alias flag that maps to the same dest.
    # In the canonical implementation, downstream code should read args.dataset.
    for action in list(parser._actions):
        opts = set(action.option_strings)
        if "--dataset" in opts and getattr(action, "required", False):
            # already has --dataset required; just add alias --dataset-path if missing
            if "--dataset-path" not in opts:
                action.option_strings.append("--dataset-path")
            return

    # If the original script used --dataset-path instead, add required --dataset as alias.
    parser.add_argument(
        "--dataset",
        "--dataset-path",
        dest="dataset",
        required=True,
        help="Path to dataset (.zip or extracted dir)",
    )
