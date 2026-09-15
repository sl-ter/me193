from PIL import Image, ImageFilter


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def to_binary(image: Image.Image, threshold: int = 128) -> Image.Image:
    grayscale = to_grayscale(image)
    return grayscale.point(lambda pixel: 255 if pixel >= threshold else 0)


def erode(image: Image.Image, iterations: int = 0) -> Image.Image:
    for _ in range(iterations):
        image = image.filter(ImageFilter.MinFilter(3))
    return image


def dilate(image: Image.Image, iterations: int = 0) -> Image.Image:
    for _ in range(iterations):
        image = image.filter(ImageFilter.MaxFilter(3))
    return image
