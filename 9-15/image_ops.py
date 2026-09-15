from PIL import Image


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def to_binary(image: Image.Image, threshold: int = 128) -> Image.Image:
    grayscale = to_grayscale(image)
    return grayscale.point(lambda pixel: 255 if pixel >= threshold else 0)
