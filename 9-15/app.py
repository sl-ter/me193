import io
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename

from image_ops import dilate, erode, to_binary

app = Flask(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

# Keep processing snappy even on large photos, since sliders re-render on every move
MAX_DIM = 1000

# Single in-memory slot for the currently loaded image. This is a local,
# single-user tool (not a multi-session web app), so global state is fine.
current_image: Image.Image | None = None
current_stem = "image"


def render_pipeline(threshold: int, erosion: int, dilation: int) -> Image.Image:
    result = to_binary(current_image, threshold)
    result = erode(result, erosion)
    result = dilate(result, dilation)
    return result


def params_from_request() -> tuple[int, int, int]:
    threshold = request.args.get("threshold", 128, type=int)
    erosion = request.args.get("erosion", 0, type=int)
    dilation = request.args.get("dilation", 0, type=int)
    return threshold, erosion, dilation


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    global current_image, current_stem

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify(error="No image provided."), 400

    image = Image.open(file.stream).convert("RGB")
    image.thumbnail((MAX_DIM, MAX_DIM))
    current_image = image
    current_stem = Path(file.filename).stem

    return jsonify(ok=True, width=image.width, height=image.height)


@app.route("/render")
def render():
    if current_image is None:
        return "", 404

    threshold, erosion, dilation = params_from_request()
    result = render_pipeline(threshold, erosion, dilation)

    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    return Response(
        buffer.getvalue(), mimetype="image/png", headers={"Cache-Control": "no-store"}
    )


@app.route("/download")
def download():
    if current_image is None:
        return "", 404

    threshold, erosion, dilation = params_from_request()
    result = render_pipeline(threshold, erosion, dilation)

    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = secure_filename(
        f"{current_stem}_9-15_threshold-{threshold}_erode-{erosion}_dilate-{dilation}.png"
    )
    output_path = OUTPUT_DIR / filename
    result.save(output_path)

    return send_file(output_path, as_attachment=True)


if __name__ == "__main__":
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True)
