"""
SSRF Protection and Safe HTTP Fetching Engine for Sovereign AI — SIH26117.
Enforces strict boundaries:
- Only HTTP/HTTPS schemes
- Blocks localhost, 127.0.0.1, 0.0.0.0, private IPs (RFC 1918), link-local, cloud metadata
- Validates all redirects against SSRF filter before following
- Enforces connection timeouts, read timeouts, and response size limits
"""

import ipaddress
import socket
import ssl
import urllib.parse
import urllib.request
from typing import Tuple, Optional


# ================================================================
# CONSTANTS & LIMITS
# ================================================================

ALLOWED_SCHEMES = {"http", "https"}
MAX_REDIRECTS = 3
DEFAULT_CONNECT_TIMEOUT = 8  # seconds
DEFAULT_READ_TIMEOUT = 10     # seconds
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB max download
MAX_EXTRACTED_TEXT_CHARS = 200_000   # 200,000 characters max

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}

BLOCKED_EXACT_IPS = {
    "169.254.169.254",  # AWS/GCP/Azure link-local metadata
    "169.254.169.253",  # DNS/DHCP link-local metadata
    "100.100.100.200",  # Alibaba Cloud metadata
    "0.0.0.0",
    "127.0.0.1",
    "::1",
    "::",
}


# ================================================================
# CUSTOM EXCEPTIONS
# ================================================================

class SSRFSecurityError(Exception):
    """Raised when a URL attempts to access private, local, or internal addresses."""
    pass


class URLFetchTimeoutError(Exception):
    """Raised when URL fetch times out."""
    pass


class URLSizeLimitExceededError(Exception):
    """Raised when the fetched page exceeds the maximum allowed size."""
    pass


# ================================================================
# SSRF VALIDATION
# ================================================================

def is_ip_blocked(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> Tuple[bool, str]:
    """
    Checks if an IP address is private, loopback, link-local, multicast,
    or otherwise restricted.
    """
    ip_str = str(ip_obj)
    if ip_str in BLOCKED_EXACT_IPS:
        return True, f"Blocked metadata / loopback address: {ip_str}"

    if ip_obj.is_loopback:
        return True, f"Loopback address blocked: {ip_str}"

    if ip_obj.is_private:
        return True, f"Private internal address (RFC 1918) blocked: {ip_str}"

    if ip_obj.is_link_local:
        return True, f"Link-local address blocked: {ip_str}"

    if ip_obj.is_unspecified:
        return True, f"Unspecified address blocked: {ip_str}"

    if ip_obj.is_multicast:
        return True, f"Multicast address blocked: {ip_str}"

    if ip_obj.is_reserved:
        return True, f"Reserved address blocked: {ip_str}"

    return False, ""


def validate_safe_url(url: str) -> str:
    """
    Validates that a URL is a legitimate, publicly routable HTTP/HTTPS URL.
    Resolves DNS and verifies that resolved IP addresses are public.
    Raises SSRFSecurityError if any check fails.
    Returns the normalized URL string.
    """
    if not url or not isinstance(url, str):
        raise SSRFSecurityError("URL is required and must be a string.")

    cleaned_url = url.strip()
    parsed = urllib.parse.urlparse(cleaned_url)

    # 1. Scheme check
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SSRFSecurityError(
            f"Invalid scheme '{scheme}'. Only HTTP and HTTPS are permitted."
        )

    # 2. Hostname check
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise SSRFSecurityError("URL does not contain a valid hostname.")

    if hostname in BLOCKED_HOSTNAMES:
        raise SSRFSecurityError(f"Access to hostname '{hostname}' is strictly blocked.")

    # Check for localhost patterns (e.g. *.localhost)
    if hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise SSRFSecurityError(f"Access to local hostname '{hostname}' is strictly blocked.")

    # 3. Direct IP format check
    try:
        direct_ip = ipaddress.ip_address(hostname)
        blocked, reason = is_ip_blocked(direct_ip)
        if blocked:
            raise SSRFSecurityError(reason)
        return cleaned_url
    except ValueError:
        # Hostname is a domain name, proceed to DNS resolution
        pass

    # 4. Port check (prevent port scanning on internal services like 3306, 6379, etc.)
    port = parsed.port
    if port is not None and port not in (80, 443, 8080, 8443):
        # Disallow connections to typical database / local service ports
        if port in (3306, 5432, 6379, 27017, 9200, 11434, 8000, 22, 21, 25):
            raise SSRFSecurityError(f"Access to port {port} is restricted for security.")

    # 5. DNS Resolution & IP validation
    try:
        addr_info = socket.getaddrinfo(hostname, port or (443 if scheme == "https" else 80))
    except socket.gaierror as e:
        raise SSRFSecurityError(f"DNS resolution failed for '{hostname}': {e}")
    except Exception as e:
        raise SSRFSecurityError(f"Network error resolving '{hostname}': {e}")

    if not addr_info:
        raise SSRFSecurityError(f"Could not resolve any IP address for '{hostname}'.")

    # Check all resolved IP addresses
    for entry in addr_info:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
            blocked, reason = is_ip_blocked(resolved_ip)
            if blocked:
                raise SSRFSecurityError(
                    f"Host '{hostname}' resolves to restricted IP {ip_str}: {reason}"
                )
        except ValueError:
            continue

    return cleaned_url


# ================================================================
# SAFE REDIRECT HANDLER
# ================================================================

class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Ensures that every redirect is inspected and validated before
    being followed. Prevents redirect-based SSRF attacks.
    """

    def __init__(self, max_redirects: int = MAX_REDIRECTS):
        super().__init__()
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > self.max_redirects:
            raise SSRFSecurityError(
                f"Too many redirects (maximum {self.max_redirects} allowed)."
            )

        # Validate the redirect target URL against SSRF checks
        try:
            validated_url = validate_safe_url(newurl)
        except SSRFSecurityError as e:
            raise SSRFSecurityError(
                f"Redirect to '{newurl}' was blocked by SSRF protection: {e}"
            )

        return super().redirect_request(req, fp, code, msg, headers, validated_url)


# ================================================================
# SAFE URL FETCHER
# ================================================================

def fetch_url_safely(
    url: str,
    timeout: int = DEFAULT_READ_TIMEOUT,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> Tuple[str, str, str]:
    """
    Fetches a URL safely with SSRF protection, size caps, and timeouts.
    Returns:
        (html_content, final_url, content_type)
    """
    validated_url = validate_safe_url(url)

    # Setup SSL context (standard verification)
    ssl_context = ssl.create_default_context()

    # Build opener with redirect validator
    redirect_handler = SafeRedirectHandler(max_redirects=MAX_REDIRECTS)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_context),
        urllib.request.HTTPHandler(),
        redirect_handler,
    )

    # Standard modern browser User-Agent and headers
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-CH-UA": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    req = urllib.request.Request(validated_url, headers=headers)

    try:
        with opener.open(req, timeout=timeout) as response:
            final_url = response.geturl()
            # Double-check final URL after redirects
            validate_safe_url(final_url)

            content_type = response.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type.lower():
                parts = content_type.lower().split("charset=")
                if len(parts) > 1:
                    charset = parts[1].split(";")[0].strip()

            # Read with size limit
            chunks = []
            total_read = 0
            while True:
                chunk = response.read(65536)  # 64 KB chunks
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > max_bytes:
                    raise URLSizeLimitExceededError(
                        f"Page size exceeds maximum limit of {max_bytes // (1024 * 1024)}MB."
                    )
                chunks.append(chunk)

            raw_bytes = b"".join(chunks)

            try:
                text_content = raw_bytes.decode(charset, errors="replace")
            except Exception:
                text_content = raw_bytes.decode("utf-8", errors="replace")

            return text_content, final_url, content_type

    except urllib.error.HTTPError as e:
        if e.code == 999:
            raise RuntimeError(
                "Access blocked by website anti-scraping / login wall (HTTP 999). "
                "This platform (e.g. LinkedIn) requires user login authentication and blocks automated public fetch requests."
            )
        elif e.code in (401, 403):
            reason_msg = e.reason if e.reason and str(e.reason).lower() != "none" else "Forbidden"
            raise RuntimeError(
                f"Access restricted by target website (HTTP {e.code} {reason_msg}). "
                "The page requires user login authentication or is protected by anti-bot verification."
            )
        elif e.code == 404:
            raise RuntimeError("Page not found (HTTP 404). Please verify the public URL.")
        reason_str = str(e.reason) if e.reason and str(e.reason).lower() != "none" else f"status code {e.code}"
        raise RuntimeError(f"HTTP {e.code} error fetching URL ({reason_str})")
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            raise URLFetchTimeoutError("Connection timed out while fetching the public URL.")
        reason_str = str(e.reason) if e.reason and str(e.reason).lower() != "none" else "Unknown error"
        raise RuntimeError(f"Network error fetching URL: {reason_str}")
    except socket.timeout:
        raise URLFetchTimeoutError("Connection timed out while fetching the public URL.")
