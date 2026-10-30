"""
Middleware for injecting global galaxy background script into HTML responses.
"""

class GalaxyBackgroundMiddleware:
    """
    Automatically injects /static/js/galaxy-bg.js into all HTML responses
    so the galaxy background runs on every single page of the website.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if response.status_code == 200 and "text/html" in content_type:
            try:
                content = response.content.decode("utf-8")
                tag = '<script src="/static/js/galaxy-bg.js" defer></script>'
                if tag not in content and "/static/js/galaxy-bg.js" not in content:
                    if "</body>" in content:
                        content = content.replace("</body>", f"{tag}</body>", 1)
                    elif "</html>" in content:
                        content = content.replace("</html>", f"{tag}</html>", 1)
                    else:
                        content += tag
                    response.content = content.encode("utf-8")
                    if response.has_header("Content-Length"):
                        response["Content-Length"] = str(len(response.content))
            except UnicodeDecodeError:
                pass
        return response
