import base64
import io
from pathlib import Path

from flask import Flask, render_template, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename

from image_ops import to_binary, to_grayscale

app = Flask(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    file = request.files.get("image")
    if not file or file.filename == "":
        return render_template("index.html", error="Please choose an image.")

    mode = request.form.get("mode", "grayscale")
    threshold = int(request.form.get("threshold", 128))

    image = Image.open(file.stream)
    if mode == "binarize":
        result = to_binary(image, threshold)
        tag = f"9-15_binarized_{threshold}"
    else:
        result = to_grayscale(image)
        tag = "9-15_grayscale"

    # Save a copy tagged with today's date, alongside the browser preview
    output_name = f"{Path(file.filename).stem}_{tag}.png"
    result.save(OUTPUT_DIR / output_name)

    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    return render_template(
        "index.html",
        result_image=encoded,
        output_name=output_name,
        mode=mode,
        threshold=threshold,
    )


@app.route("/download/<filename>")
def download(filename):
    return send_file(OUTPUT_DIR / secure_filename(filename), as_attachment=True)


if __name__ == "__main__":
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True)
