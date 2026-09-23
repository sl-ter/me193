import sys
from pathlib import Path

from PIL import Image

from image_ops import to_grayscale

# 1. Get the input image path from the command line
if len(sys.argv) != 2:
    print("Usage: python grayscale.py <path/to/image>")
    exit(1)

input_path = Path(sys.argv[1])

# 2. Load the image
print(f"Loading {input_path}...")
image = Image.open(input_path)

# 3. Convert it to grayscale
grayscale_image = to_grayscale(image)

# 4. Save the result, tagged with today's date
output_path = input_path.with_stem(f"{input_path.stem}_9-15_grayscale")
grayscale_image.save(output_path)

print(f"Saved grayscale image to {output_path}")
