from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import yt_dlp


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # Supaya bisa dipanggil dari browser/frontend lain (CORS preflight)
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
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

        # Opsi yt-dlp: hanya ambil metadata, JANGAN download filenya
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            # Kalau butuh cookies untuk situs tertentu, bisa tambahkan opsi di sini
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)

            # Kalau url adalah playlist, yt-dlp bisa balikin 'entries'
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
                result = {
                    "success": True,
                    "type": "video",
                    **self._simplify(info),
                }

            self._send_json(result, 200)

        except yt_dlp.utils.DownloadError as e:
            self._send_json({"success": False, "error": f"Gagal ekstrak: {str(e)}"}, 422)
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _simplify(self, info):
        formats = []
        for f in info.get("formats", []) or []:
            # Lewati format yang tidak punya url langsung
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
            # url langsung kualitas terbaik (gabungan video+audio kalau ada)
            "direct_url": info.get("url"),
        }

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
