import base64
import json
import subprocess
import os
import sys

try:
    from inferencesh import inference
    from dotenv import load_dotenv
except ImportError:
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "inferencesh", "python-dotenv"])
    from inferencesh import inference
    from dotenv import load_dotenv

load_dotenv(r"C:\Users\User\OneDrive\Desktop\projects\Crypto-trading-bot\server\.env")
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY missing from environment and .env")
    sys.exit(1)

client = inference(api_key=api_key)

map_path = r"C:\Users\User\OneDrive\Desktop\projects\Crypto-trading-bot\frontend\public\assets\tilesets\office_rpg_map.png"

with open(map_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    data_uri = f"data:image/png;base64,{encoded_string}"

print("Running Nano Banana 2 inference to extend the map to 21:9...")
result = client.run({
    "app": "google/gemini-3-1-flash-image-preview",
    "input": {
        "prompt": "Extend this 16-bit top-down RPG pixel art office map to be much wider. Outpaint the left and right edges seamlessly with more pixel art desks, office plants, and retro computers. Extremely cohesive styling. Maintain current layout in the middle.",
        "images": [data_uri],
        "aspect_ratio": "21:9"
    }
})

print("Parsing result...")
if "output" in result and "images" in result["output"]:
    b64_out = result["output"]["images"][0]
    if b64_out.startswith("data:image"):
        b64_out = b64_out.split(",")[1]
    
    out_path = r"C:\Users\User\OneDrive\Desktop\projects\Crypto-trading-bot\frontend\public\assets\tilesets\office_rpg_map_extended.png"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64_out))
    print(f"Successfully saved extended map to {out_path}")
else:
    print(f"Failed. Output: {result}")
