from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe one kitchen keyframe with a Hugging Face vision-language model.")
    parser.add_argument("--model", default="HuggingFaceTB/SmolVLM2-500M-Video-Instruct")
    parser.add_argument("--image", required=True)
    parser.add_argument("--prompt", default=(
        "Describe the kitchen scene. List visible objects and spatial relationships. "
        "Be conservative. If uncertain, say unknown. Return concise JSON with objects and relationships."
    ))
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()

    image_path = Path(args.image)
    image = Image.open(image_path).convert("RGB")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    ).to(device)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": args.prompt},
            ],
        }
    ]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=prompt, images=[image], return_tensors="pt").to(device)

    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)

    text = processor.batch_decode(generated, skip_special_tokens=True)[0]
    print(json.dumps({"model": args.model, "image": str(image_path), "device": device, "response": text}, indent=2))


if __name__ == "__main__":
    main()
