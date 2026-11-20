"""Who is asking, and may they. The guards every router uses, plus the address checks the gate needs."""

import ipaddress
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from . import auth, config, ctx


_CDN_RANGES = None


def _from_cdn(addr: str) -> bool:
    global _CDN_RANGES
    import ipaddress
    if _CDN_RANGES is None:
        ranges = config.env("CLIPSORA_CDN_RANGES") or (
            "173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 "
            "190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 "
            "104.24.0.0/14 172.64.0.0/13 131.0.72.0/22 2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 "
            "2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32")
        _CDN_RANGES = [ipaddress.ip_network(r) for r in ranges.replace(",", " ").split()]
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in n for n in _CDN_RANGES)


_PROXY_CIDRS = ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "169.254.0.0/16",
                "::1/128", "fc00::/7", "fe80::/10")


_PROXY_RANGES = [ipaddress.ip_network(r) for r in _PROXY_CIDRS]


def _trust_proxy() -> bool:
    return (config.env("CLIPSORA_TRUST_PROXY") or "").strip().lower() not in ("", "0", "false", "no")


def _valid_ip(text: str) -> str:
    """The address as text if it really is an IP address, otherwise ""."""
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return ""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return str(ip)


def _from_proxy(addr: str) -> bool:
    clean = _valid_ip(addr)
    if not clean:
        return False
    ip = ipaddress.ip_address(clean)
    return any(ip in n for n in _PROXY_RANGES)


def _ip(request: Request) -> str:
    """The visitor's address, used for rate limits. The connection's own address, or the one the proxy in front
    reports (CLIPSORA_TRUST_PROXY). If that connection comes from the CDN, the CDN's header names the real visitor
    (CLIPSORA_CLIENT_IP_HEADER). The header is believed only when the CDN really sent the request, so nobody can
    pick their own address by sending it themselves.

    The proxy adds the address it saw at the END of X-Forwarded-For. Everything before that was written by the
    visitor, so only the last entry is believed, and only when the connection came from a proxy on a private address."""
    direct = request.client.host if request.client else ""
    peer = direct
    fwd = ",".join(request.headers.getlist("x-forwarded-for"))
    if _trust_proxy() and fwd and _from_proxy(direct):
        peer = _valid_ip(fwd.rsplit(",", 1)[-1].strip()) or direct
    named = config.env("CLIPSORA_CLIENT_IP_HEADER")
    if named and request.headers.get(named) and _from_cdn(peer):
        return _valid_ip(request.headers[named].split(",")[0].strip()[:64]) or peer
    return peer


def _from_here(req, must_say=False) -> bool:
    """Did this change come from Clipsora's own page, and not from another website?

    The browser's own answer is trusted first: it marks every request "same-origin" or not, and a web page cannot
    fake that mark. Comparing the page's address with the address the request arrived at is only the fallback,
    because that comparison goes wrong when something in between rewrites either of them (a proxy, an antivirus
    web shield, a browser extension), which made every save fail with "Cross-site requests are not allowed"."""
    if (req.headers.get("sec-fetch-site") or "").lower() == "same-origin":
        return True
    origin = (req.headers.get("origin") or "").rstrip("/").lower()
    if not origin:
        return not must_say
    return urlparse(origin).netloc == (req.headers.get("host") or "").lower() or origin == config.PUBLIC_URL.lower()


def _own_address(host: str) -> bool:
    """Is this the address Clipsora is really reached by? A number (127.0.0.1, 192.168.1.20), "localhost", or the
    host in CLIPSORA_PUBLIC_URL."""
    import ipaddress
    name = host.strip().lower()
    name = name[1:name.index("]")] if name.startswith("[") and "]" in name else name.rsplit(":", 1)[0] if ":" in name else name
    if name in ("localhost", urlparse(config.PUBLIC_URL).hostname or "") or name.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


def _me(request: Request):
    return request.state.user


def _admin(request: Request):
    """The signed-in admin, read from the database for this very request. Anyone else gets "not found"."""
    u = getattr(request.state, "user", None)
    if not u or not u.is_admin or u.disabled:
        raise HTTPException(404)
    return u


def _need_verified():
    if not auth.is_verified(ctx.uid()):
        raise HTTPException(403, "Confirm your email first. We sent you a link when you signed up; you can send a new one from the banner at the top.")
