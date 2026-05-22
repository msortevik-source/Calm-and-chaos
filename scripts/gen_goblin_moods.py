"""One-shot: generate 3 mood variants of the goblin via Nano Banana, with the existing sprite as reference."""
import asyncio
import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

load_dotenv("/app/backend/.env")
API_KEY = os.environ["EMERGENT_LLM_KEY"]
REF_PATH = Path("/tmp/goblin_src.png")  # original full-size reference downloaded earlier
OUT_DIR = Path("/app/frontend/public")

CHARACTER = (
    "the SAME goblin character from the reference image — small friendly goblin, "
    "muted green skin, freckles, brown eyes, dark messy hair in a top bun with a small "
    "green leaf in it, pointed ears, wearing the same dark charcoal hoodie. KEEP THE "
    "CHARACTER VISUALLY IDENTICAL to the reference."
)

PROMPTS = {
    "morning": (
        f"{CHARACTER} Pose: sleepy morning — eyes barely open, soft droopy lids, hood "
        "pulled up over the bun, sitting cross-legged on the floor, both hands cradling "
        "the 'emotional support goblin' mug close to her chest with steam rising. "
        "Soft warm peaceful expression. Plain white background. Full body. Hand-drawn "
        "illustration style matching the reference."
    ),
    "evening": (
        f"{CHARACTER} Pose: evening wind-down — slumped sideways against an unseen "
        "cushion, mug set down beside her, one hand limp in her lap, eyes half-closed "
        "soft peaceful. Tired but content. Plain white background. Full body. "
        "Hand-drawn illustration style matching the reference."
    ),
    "late_night": (
        f"{CHARACTER} Pose: late-night dry stare — sitting upright, ONE eye half-open "
        "and dryly judging the viewer, other eye closed, slight smirk, mug still in "
        "hand. Dry, observant, faintly exasperated. Plain white background. Full body. "
        "Hand-drawn illustration style matching the reference."
    ),
}

def clean_and_save(image_bytes: bytes, dest: Path):
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    # Knock out near-white background
    data = list(img.getdata())
    new_data = []
    for r, g, b, a in data:
        if r > 240 and g > 240 and b > 240:
            new_data.append((255, 255, 255, 0))
        elif r > 220 and g > 220 and b > 220:
            brightness = (r + g + b) / 3
            alpha = int(255 * (1 - (brightness - 220) / 35))
            new_data.append((r, g, b, max(0, min(255, alpha))))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    # Resize to 600px tall
    target_h = 600
    ratio = target_h / img.height
    img = img.resize((int(img.width * ratio), target_h), Image.LANCZOS)
    img.save(dest, optimize=True)
    print(f"  wrote {dest} {img.size} {os.path.getsize(dest)/1024:.0f}KB")

async def gen_one(mood: str, prompt: str, ref_b64: str):
    print(f"=== generating {mood} ===")
    chat = LlmChat(
        api_key=API_KEY,
        session_id=f"goblin-mood-{mood}",
        system_message="You are an illustrator. Generate ONE image only.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    msg = UserMessage(text=prompt, file_contents=[ImageContent(ref_b64)])
    try:
        text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        print(f"  FAILED: {e}")
        return False
    if not images:
        print(f"  no image returned. text: {text[:160]}")
        return False
    img_bytes = base64.b64decode(images[0]["data"])
    clean_and_save(img_bytes, OUT_DIR / f"goblin-{mood}.png")
    return True

async def main():
    with open(REF_PATH, "rb") as f:
        ref_b64 = base64.b64encode(f.read()).decode("utf-8")
    print(f"reference: {REF_PATH} ({len(ref_b64)} chars b64)")
    results = {}
    for mood, prompt in PROMPTS.items():
        ok = await gen_one(mood, prompt, ref_b64)
        results[mood] = ok
    print("\nresults:", results)

if __name__ == "__main__":
    asyncio.run(main())
