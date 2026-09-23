import sys
from pathlib import Path

from PIL import Image

from image_ops import to_binary

# 1. Get the input image path and threshold from the command line
if len(sys.argv) not in (2, 3):
    print("Usage: python binarize.py <path/to/image> [threshold=128]")
    exit(1)

input_path = Path(sys.argv[1])
threshold = int(sys.argv[2]) if len(sys.argv) == 3 else 128

# 2. Load the image
print(f"Loading {input_path}...")
image = Image.open(input_path)

# 3. Binarize it (every pixel becomes pure black or pure white)
binary_image = to_binary(image, threshold)

# 4. Save the result, tagged with today's date
output_path = input_path.with_stem(f"{input_path.stem}_9-15_binarized_{threshold}")
binary_image.save(output_path)

print(f"Saved binarized image to {output_path}")
