import hashlib
import os

import filetype
from flask import Flask, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["400 per day", "60 per hour"],
    storage_uri="memory://",
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
BASE_URL = ""  # Set this to your public base URL
PORT = 16384
UPLOAD_FOLDER = "artwork_uploads"

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_hash(file_content: bytes) -> str:
    return hashlib.md5(file_content).hexdigest()


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large. Maximum size is 8MB."}), 413


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded. Try again later."}), 429


@app.route("/upload", methods=["POST"])
@limiter.limit("10 per minute")
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file.filename:
        secure_name = secure_filename(file.filename)
        if not secure_name:
            return jsonify({"error": "Invalid filename"}), 400

    file_content = file.read()

    if len(file_content) == 0:
        return jsonify({"error": "Empty file not allowed"}), 400

    if kind := filetype.guess(file_content):
        if kind.extension not in ALLOWED_EXTENSIONS:
            return jsonify({"error": "File type not allowed"}), 400
        extension = kind.extension
    else:
        if not (file.filename and allowed_file(file.filename)):
            return jsonify({"error": "Cannot determine file type"}), 400
        extension = file.filename.rsplit(".", 1)[1].lower()

    file_hash = get_file_hash(file_content)
    filename = f"{file_hash}.{extension}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    os.makedirs(UPLOAD_FOLDER, mode=0o755, exist_ok=True)

    if not os.path.exists(file_path):
        try:
            with open(file_path, "wb") as f:
                f.write(file_content)

        except IOError:
            return jsonify({"error": "Failed to save file"}), 500

    file_url = f"{BASE_URL}/files/{filename}"
    return jsonify({"url": file_url})


@app.route(
    "/files/<filename>"
)  # Serving files through a web server like Nginx or Apache would be more efficient
@limiter.limit("100 per minute")
def uploaded_file(filename: str):
    if not (secure_name := secure_filename(filename)) or secure_name != filename:
        return jsonify({"error": "Invalid filename"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, secure_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(UPLOAD_FOLDER, secure_name)


@app.route("/health")
def health_check():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
