from urllib.parse import urlparse

def _get_script_name(url: str) -> str:
    """Extract the script name from the git URL."""
    path = urlparse(url).path
    return path.rstrip("/").split("/")[-1]
