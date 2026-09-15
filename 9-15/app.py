import io
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename

from image_ops import apply_operation, array_to_image, to_binary_array

app = Flask(__name__)

# Keep processing snappy even on large photos, since sliders re-render on every move
MAX_DIM = 1000

# Single in-memory slot for the currently loaded image. This is a local,
# single-user tool (not a multi-session web app), so global state is fine.
current_image: Image.Image | None = None
current_stem = "image"


def params_from_request() -> tuple[int, str, int, str]:
    threshold = request.args.get("threshold", 128, type=int)
    operation = request.args.get("operation", "none")
    amount = request.args.get("amount", 1, type=int)
    pattern = request.args.get("pattern", "isolated")
    return threshold, operation, amount, pattern


def render_pipeline(threshold: int, operation: str, amount: int, pattern: str) -> Image.Image:
    binary = to_binary_array(current_image, threshold)
    result = apply_operation(binary, operation, amount, pattern)
    return array_to_image(result)


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

    result = render_pipeline(*params_from_request())

    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    return Response(
        buffer.getvalue(), mimetype="image/png", headers={"Cache-Control": "no-store"}
    )


@app.route("/download")
def download():
    if current_image is None:
        return "", 404

    threshold, operation, amount, pattern = params_from_request()
    result = render_pipeline(threshold, operation, amount, pattern)

    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    buffer.seek(0)

    filename = secure_filename(
        f"{current_stem}_9-15_{operation}_threshold-{threshold}_amount-{amount}.png"
    )
    return send_file(buffer, mimetype="image/png", as_attachment=True, download_name=filename)


if __name__ == "__main__":
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True)
