"""Link Dashboard — a small web app with an incomplete interface.

This is a demo project for reeree. It has a web UI with obvious gaps:
- The add-link form doesn't work
- Search is a stub
- No error handling on the API
- Tests are incomplete
- CSS is minimal

A good reeree plan would be:
  1. Fix the add-link form (POST handler, validation)
  2. Implement search (filter by title/url/tag)
  3. Add tag management
  4. Fix error handling on API routes
  5. Write the missing tests
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from pathlib import Path

DATA_FILE = Path(__file__).parent / "links.json"


def load_links():
    """Load links from JSON file."""
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return []


def save_links(links):
    """Save links to JSON file."""
    DATA_FILE.write_text(json.dumps(links, indent=2))


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the link dashboard."""

    def do_GET(self):
        if self.path == "/":
            self._serve_dashboard()
        elif self.path == "/api/links":
            self._serve_links_api()
        elif self.path == "/api/search":
            # TODO: implement search
            self.send_response(501)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "search not implemented"}).encode())
        elif self.path == "/api/tags":
            # TODO: implement tag listing
            self.send_response(501)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "tags not implemented"}).encode())
        elif self.path == "/style.css":
            self._serve_css()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/links":
            # TODO: implement add link
            # Should read JSON body, validate url+title, append to links, save
            self.send_response(501)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "add link not implemented"}).encode())
        elif self.path == "/api/links/delete":
            # TODO: implement delete
            self.send_response(501)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "delete not implemented"}).encode())
        else:
            self.send_error(404)

    def _serve_dashboard(self):
        """Serve the main dashboard HTML."""
        html = DASHBOARD_HTML
        links = load_links()
        # Render link rows
        rows = ""
        for i, link in enumerate(links):
            tags = ", ".join(link.get("tags", []))
            rows += f"""
            <tr>
                <td><a href="{link['url']}" target="_blank">{link.get('title', link['url'])}</a></td>
                <td>{link['url']}</td>
                <td>{tags}</td>
                <td>
                    <!-- TODO: delete button doesn't work -->
                    <button class="btn-delete" onclick="deleteLink({i})">delete</button>
                </td>
            </tr>"""
        html = html.replace("{{LINK_ROWS}}", rows)
        html = html.replace("{{LINK_COUNT}}", str(len(links)))

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _serve_links_api(self):
        """Serve links as JSON."""
        links = load_links()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(links).encode())

    def _serve_css(self):
        """Serve the stylesheet."""
        css_path = Path(__file__).parent / "style.css"
        if css_path.exists():
            css = css_path.read_text()
        else:
            css = "/* no stylesheet yet */"
        self.send_response(200)
        self.send_header("Content-Type", "text/css")
        self.end_headers()
        self.wfile.write(css.encode())

    def log_message(self, format, *args):
        """Quieter logging."""
        pass


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Link Dashboard</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div class="container">
        <h1>Link Dashboard</h1>
        <p class="subtitle">{{LINK_COUNT}} links saved</p>

        <!-- Add Link Form — BROKEN: form submits but handler returns 501 -->
        <div class="add-form">
            <h2>Add Link</h2>
            <form id="add-form">
                <input type="text" id="url" placeholder="https://..." required>
                <input type="text" id="title" placeholder="Title">
                <input type="text" id="tags" placeholder="Tags (comma-separated)">
                <button type="submit">Add</button>
            </form>
            <div id="form-error" class="error" style="display:none"></div>
        </div>

        <!-- Search — STUB: just a text box that does nothing -->
        <div class="search">
            <input type="text" id="search" placeholder="Search links... (not implemented)">
        </div>

        <!-- Link Table -->
        <table>
            <thead>
                <tr>
                    <th>Title</th>
                    <th>URL</th>
                    <th>Tags</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {{LINK_ROWS}}
            </tbody>
        </table>
    </div>

    <script>
    // Add link form handler — submits to API but gets 501
    document.getElementById('add-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('url').value;
        const title = document.getElementById('title').value;
        const tags = document.getElementById('tags').value.split(',').map(t => t.trim()).filter(Boolean);

        try {
            const resp = await fetch('/api/links', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url, title, tags})
            });
            if (resp.ok) {
                window.location.reload();
            } else {
                const data = await resp.json();
                document.getElementById('form-error').textContent = data.error || 'Failed';
                document.getElementById('form-error').style.display = 'block';
            }
        } catch (err) {
            document.getElementById('form-error').textContent = err.message;
            document.getElementById('form-error').style.display = 'block';
        }
    });

    // Delete handler — calls API but gets 501
    async function deleteLink(index) {
        try {
            const resp = await fetch('/api/links/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index})
            });
            if (resp.ok) {
                window.location.reload();
            }
        } catch (err) {
            console.error(err);
        }
    }

    // Search — TODO: wire up to /api/search
    document.getElementById('search').addEventListener('input', (e) => {
        // Not implemented — should filter the table or call API
        console.log('search not implemented:', e.target.value);
    });
    </script>
</body>
</html>
"""


def main():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Link Dashboard running at http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
