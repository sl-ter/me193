import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.morphology import skeletonize as skimage_skeletonize

STRUCTURE = np.ones((3, 3), dtype=bool)  # 8-connected neighborhood

# Hit-or-miss structuring element pairs: structure1 must match the
# foreground, structure2 must match the background, at each position.
_ISOLATED_FG = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=bool)
_ISOLATED_BG = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=bool)
_CORNER_FG = np.array([[0, 0, 0], [0, 1, 1], [0, 1, 0]], dtype=bool)
_CORNER_BG = np.array([[1, 1, 0], [1, 0, 0], [0, 0, 0]], dtype=bool)

HIT_OR_MISS_PATTERNS = {
    "isolated": (_ISOLATED_FG, _ISOLATED_BG),
    "corner-top-left": (_CORNER_FG, _CORNER_BG),
    "corner-top-right": (np.rot90(_CORNER_FG), np.rot90(_CORNER_BG)),
    "corner-bottom-right": (np.rot90(_CORNER_FG, 2), np.rot90(_CORNER_BG, 2)),
    "corner-bottom-left": (np.rot90(_CORNER_FG, 3), np.rot90(_CORNER_BG, 3)),
}


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def to_binary(image: Image.Image, threshold: int = 128) -> Image.Image:
    grayscale = to_grayscale(image)
    return grayscale.point(lambda pixel: 255 if pixel >= threshold else 0)


def to_binary_array(image: Image.Image, threshold: int = 128) -> np.ndarray:
    return np.array(to_grayscale(image)) >= threshold


def array_to_image(array: np.ndarray) -> Image.Image:
    return Image.fromarray(array.astype(np.uint8) * 255, mode="L")


def erode(array: np.ndarray, iterations: int = 1) -> np.ndarray:
    return ndimage.binary_erosion(array, structure=STRUCTURE, iterations=iterations)


def dilate(array: np.ndarray, iterations: int = 1) -> np.ndarray:
    return ndimage.binary_dilation(array, structure=STRUCTURE, iterations=iterations)


def opening(array: np.ndarray, iterations: int = 1) -> np.ndarray:
    return ndimage.binary_opening(array, structure=STRUCTURE, iterations=iterations)


def closing(array: np.ndarray, iterations: int = 1) -> np.ndarray:
    return ndimage.binary_closing(array, structure=STRUCTURE, iterations=iterations)


def boundary(array: np.ndarray, thickness: int = 1) -> np.ndarray:
    return array & ~erode(array, thickness)


def skeletonize(array: np.ndarray) -> np.ndarray:
    return skimage_skeletonize(array)


def prune(array: np.ndarray, length: int = 5) -> np.ndarray:
    skeleton = skeletonize(array)
    neighbor_kernel = np.ones((3, 3), dtype=np.uint8)
    for _ in range(length):
        neighbor_count = (
            ndimage.convolve(skeleton.astype(np.uint8), neighbor_kernel, mode="constant", cval=0)
            - skeleton
        )
        endpoints = skeleton & (neighbor_count == 1)
        skeleton = skeleton & ~endpoints
    return skeleton


def hit_or_miss(array: np.ndarray, pattern: str) -> np.ndarray:
    structure1, structure2 = HIT_OR_MISS_PATTERNS[pattern]
    return ndimage.binary_hit_or_miss(array, structure1=structure1, structure2=structure2)


OPERATIONS = {
    "none": lambda array, amount, pattern: array,
    "erosion": lambda array, amount, pattern: erode(array, amount),
    "dilation": lambda array, amount, pattern: dilate(array, amount),
    "opening": lambda array, amount, pattern: opening(array, amount),
    "closing": lambda array, amount, pattern: closing(array, amount),
    "boundary": lambda array, amount, pattern: boundary(array, amount),
    "skeleton": lambda array, amount, pattern: skeletonize(array),
    "prune": lambda array, amount, pattern: prune(array, amount),
    "hit_or_miss": lambda array, amount, pattern: hit_or_miss(array, pattern),
}


def apply_operation(array: np.ndarray, operation: str, amount: int, pattern: str) -> np.ndarray:
    return OPERATIONS.get(operation, OPERATIONS["none"])(array, amount, pattern)
