from pathlib import Path
import ollama


MODEL_NAME = "qwen2.5vl:3b"


def analyze_image(image_path, question):

    # Convert to absolute path
    image_path = Path(image_path).resolve()

    print("Image path:")
    print(image_path)

    print("Image exists:", image_path.exists())

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": question,
                "images": [str(image_path)],
            }
        ],
    )

    return response["message"]["content"]


if __name__ == "__main__":

    image_path = "sovereign-ai/test.jpeg"

    question = """
Analyze the image and return ONLY valid JSON.

Use exactly this structure:

{
  "visible_objects": [],
  "visible_equipment": [],
  "visible_text": [],
  "visible_conditions": [],
  "visible_damage": [],
  "abnormalities": [],
  "confidence": 0.0
}

Rules:
- Only report information that is actually visible.
- Do not guess.
- If nothing is visible for a field, return an empty array.
- visible_text should contain readable text from the image.
- visible_conditions should describe visible physical conditions.
- visible_damage should contain only clearly visible damage.
- abnormalities should contain only clearly visible abnormalities.
- confidence must be a number between 0 and 1.
- Return JSON only.
"""

    result = analyze_image(image_path, question)

    print("\n========================================")
    print("LOCAL VISION MODEL RESULT")
    print("========================================")
    print(result)