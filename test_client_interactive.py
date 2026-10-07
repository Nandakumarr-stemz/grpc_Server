#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import grpc

load_dotenv()

# Allow running this script directly from repo root without PYTHONPATH tweaks.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.image_processor_service.proto import image_processor_pb2, image_processor_pb2_grpc

# Config loading (JSON)
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        raise RuntimeError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive gRPC test client")
    parser.add_argument("--endpoint", default="127.0.0.1:50051", help="gRPC server endpoint")
    parser.add_argument(
        "--deadline-seconds",
        type=float,
        default=10.0,
        help="Per-request gRPC deadline in seconds",
    )
    return parser.parse_args()


def send_image(
    stub: image_processor_pb2_grpc.ImageProcessorServiceStub,
    image_path: Path,
    deadline_seconds: float,
    config: dict,
) -> dict[str, object]:
    image_bytes = image_path.read_bytes()

    api_key = config.get("API_KEY")
    if not api_key:
        raise RuntimeError("Missing API_KEY in config.json")
    print(f"Using API_KEY: {api_key}...")
    metadata = [("authorization", f"Bearer {api_key}")]

    response = stub.ProcessImage(
        image_processor_pb2.ProcessImageRequest(image_bytes=image_bytes),
        timeout=deadline_seconds,
        metadata=metadata,
    )

    return {
        "algorithm": response.algorithm,
        "type": response.type,
        "width": response.width,
        "height": response.height,
        "average_color": {
            "red": response.average_color.red,
            "green": response.average_color.green,
            "blue": response.average_color.blue,
        },
    }


def main():
    args = parse_args()
    config = load_config()

    print("Interactive image sender (tools/)")
    print("Enter image path or 'q' to quit")

    with grpc.insecure_channel(args.endpoint) as channel:
        stub = image_processor_pb2_grpc.ImageProcessorServiceStub(channel)

        while True:
            raw = input("image path> ").strip()

            if raw.lower() in {"q", "quit", "exit"}:
                break

            if not raw:
                continue

            image_path = Path(raw).expanduser()

            if not image_path.is_file():
                print(f"Not a file: {image_path}")
                continue

            try:
                result = send_image(
                    stub,
                    image_path,
                    args.deadline_seconds,
                    config,
                )
                print(json.dumps({"image": str(image_path), "result": result}, indent=2))

            except grpc.RpcError as e:
                print(f"RPC failed: {e.code().name} - {e.details()}")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    main()
