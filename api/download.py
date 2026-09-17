from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import yt_dlp
import requests

DEFAULT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# Beberapa CDN butuh Referer yang sesuai platform aslinya supaya tidak ditolak
REFERER_MAP = {
    "tiktokcdn": "https://www.tiktok.com/",
    "tiktokv": "https://www.tiktok.com/",
    "ttwstatic": "https://www.tiktok.com/",
    "muscdn": "https://www.tiktok.com/",
    "cdninstagram": "https://www.instagram.com/",
    "fbcdn": "https://www.instagram.com/",
    "twimg": "https://twitter.com/",
    "video.twimg": "https://twitter.com/",
    "pinimg": "https://www.pinterest.com/",
    "googlevideo": "https://www.youtube.com/",
}

EXT_MAP = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def guess_referer(url):
    host = urlparse(url).netloc.lower()
    for key, ref in REFERER_MAP.items():
        if key in host:
            return ref
    return None


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        action = params.get("action", [None])[0]

        if action == "stream":
            self._handle_stream(params)
        else:
            self._handle_download(params)

    # ---------- MODE 1: ambil metadata (default) ----------
    # GET /api/download?url=<url video>
    def _handle_download(self, params):
        video_url = params.get("url", [None])[0]

        if not video_url:
            self._send_json(
                {
                    "success": False,
                    "error": "Parameter 'url' wajib diisi. Contoh: /api/download?url=https://youtube.com/watch?v=xxxx",
                },
                400,
            )
            return

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)

            if "entries" in info and info["entries"] is not None:
                entries = [self._simplify(e) for e in info["entries"] if e]
                result = {
                    "success": True,
                    "type": "playlist",
                    "title": info.get("title"),
                    "total_entries": len(entries),
                    "entries": entries,
                }
            else:
                result = {"success": True, "type": "video", **self._simplify(info)}

            self._send_json(result, 200)

        except yt_dlp.utils.DownloadError as e:
            self._send_json({"success": False, "error": f"Gagal ekstrak: {str(e)}"}, 422)
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _simplify(self, info):
        formats = []
        for f in info.get("formats", []) or []:
            if not f.get("url"):
                continue
            formats.append(
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution") or f.get("format_note"),
                    "filesize": f.get("filesize") or f.get("filesize_approx"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "abr": f.get("abr"),
                    "fps": f.get("fps"),
                    "url": f.get("url"),
                }
            )

        return {
            "title": info.get("title"),
            "description": info.get("description"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "upload_date": info.get("upload_date"),
            "webpage_url": info.get("webpage_url"),
            "extractor": info.get("extractor"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "formats": formats,
            "direct_url": info.get("url"),
        }

    # ---------- MODE 2: proxy/stream file media asli ----------
    # GET /api/download?action=stream&url=<direct_url dari hasil mode 1>
    def _handle_stream(self, params):
        media_url = params.get("url", [None])[0]
        filename = params.get("filename", [None])[0]
        referer_override = params.get("referer", [None])[0]

        if not media_url:
            self._send_json(
                {"success": False, "error": "Parameter 'url' wajib diisi (link media yang mau di-download)."},
                400,
            )
            return

        headers = {"User-Agent": DEFAULT_UA}
        referer = referer_override or guess_referer(media_url)
        if referer:
            headers["Referer"] = referer

        try:
            upstream = requests.get(media_url, headers=headers, stream=True, timeout=25)
        except requests.RequestException as e:
            self._send_json({"success": False, "error": f"Gagal konek ke sumber media: {str(e)}"}, 502)
            return

        if upstream.status_code >= 400:
            self._send_json(
                {
                    "success": False,
                    "error": f"Sumber media menolak permintaan (status {upstream.status_code}). "
                    f"Kemungkinan link sudah expired, coba fetch ulang lewat mode metadata.",
                },
                upstream.status_code,
            )
            upstream.close()
            return

        content_type = upstream.headers.get("Content-Type", "application/octet-stream")
        content_length = upstream.headers.get("Content-Length")

        if not filename:
            ext = EXT_MAP.get(content_type.split(";")[0].strip(), "bin")
            filename = f"download.{ext}"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if content_length:
            self.send_header("Content-Length", content_length)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._set_cors_headers()
        self.end_headers()

        try:
            for chunk in upstream.iter_content(chunk_size=262144):
                if chunk:
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            upstream.close()

    # ---------- helper ----------
    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data, status):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._set_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
