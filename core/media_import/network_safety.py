import ipaddress
import socket
import threading
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .media_import_errors import MediaImportError, MediaImportErrorCode


@dataclass(frozen=True)
class SafeResolvedTarget:
    original_url: str = field(repr=False)
    scheme: str
    hostname: str
    port: int
    resolved_ips: tuple[str, ...]


_patch_lock = threading.Lock()
_active_policies = []
_orig_getaddrinfo = socket.getaddrinfo


def _guarded_getaddrinfo(*args, **kwargs):
    result = _orig_getaddrinfo(*args, **kwargs)
    with _patch_lock:
        policies = list(_active_policies)
    for policy in policies:
        for item in result:
            if not policy.is_ip_allowed(item[4][0]):
                raise socket.gaierror(-2, f"Blocked connection to unsafe IP: {item[4][0]}")
    return result


class SafeSocketContext:
    def __init__(self, safety_policy: "NetworkSafetyPolicy"):
        self.safety_policy = safety_policy

    def __enter__(self):
        global _orig_getaddrinfo
        with _patch_lock:
            if not _active_policies:
                _orig_getaddrinfo = socket.getaddrinfo
                socket.getaddrinfo = _guarded_getaddrinfo
            _active_policies.append(self.safety_policy)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        with _patch_lock:
            if self.safety_policy in _active_policies:
                _active_policies.remove(self.safety_policy)
            if not _active_policies:
                socket.getaddrinfo = _orig_getaddrinfo
        return False


class NetworkSafetyPolicy:
    _ALLOWED_SCHEMES = {"http", "https"}
    _DEFAULT_PORTS = {"http": 80, "https": 443}
    _CGNAT = ipaddress.ip_network("100.64.0.0/10")

    def validate_url(self, url: str) -> SafeResolvedTarget:
        if not isinstance(url, str) or not url:
            self._raise(MediaImportErrorCode.INVALID_URL, "URL is invalid")

        try:
            parsed = urlsplit(url)
            scheme = parsed.scheme.lower()
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise MediaImportError(MediaImportErrorCode.INVALID_URL, "URL is invalid") from exc

        if not scheme:
            self._raise(MediaImportErrorCode.INVALID_URL, "URL must include a scheme")
        if scheme not in self._ALLOWED_SCHEMES:
            self._raise(MediaImportErrorCode.UNSAFE_URL, "Only HTTP(S) URLs are allowed")
        if not hostname:
            self._raise(MediaImportErrorCode.INVALID_URL, "URL must include a hostname")
        if parsed.username is not None or parsed.password is not None:
            self._raise(MediaImportErrorCode.UNSAFE_URL, "URL credentials are not allowed")

        if port == 0:
            self._raise(MediaImportErrorCode.INVALID_URL, "URL port is invalid")
        if port is None:
            port = self._DEFAULT_PORTS[scheme]
        resolved_ips = self.resolve_and_validate_host(hostname, port)
        return SafeResolvedTarget(url, scheme, hostname, port, resolved_ips)

    def resolve_and_validate_host(self, hostname: str, port: int = 443) -> tuple[str, ...]:
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            literal = None

        if literal is not None:
            return (self._validate_ip(literal),)

        try:
            addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except UnicodeError as exc:
            raise MediaImportError(
                MediaImportErrorCode.INVALID_URL,
                "URL hostname is invalid",
            ) from exc
        except OSError as exc:
            raise MediaImportError(
                MediaImportErrorCode.NETWORK_ERROR,
                "Unable to resolve URL hostname",
                details={"hostname": hostname},
            ) from exc

        resolved_ips: list[str] = []
        for family, _, _, _, sockaddr in addresses:
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue
            try:
                resolved_ip = self._validate_ip(ipaddress.ip_address(sockaddr[0]))
            except ValueError as exc:
                raise MediaImportError(
                    MediaImportErrorCode.UNSAFE_URL,
                    "Hostname resolved to an invalid IP address",
                    details={"hostname": hostname},
                ) from exc
            if resolved_ip not in resolved_ips:
                resolved_ips.append(resolved_ip)

        if not resolved_ips:
            raise MediaImportError(
                MediaImportErrorCode.NETWORK_ERROR,
                "URL hostname did not resolve to an IP address",
                details={"hostname": hostname},
            )
        return tuple(resolved_ips)

    def validate_redirect(self, url: str) -> SafeResolvedTarget:
        return self.validate_url(url)

    def is_ip_allowed(self, ip_str: str) -> bool:
        try:
            address = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        try:
            self._validate_ip(address)
        except MediaImportError:
            return False
        return True

    @classmethod
    def _validate_ip(cls, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
        effective_address = (
            address.ipv4_mapped
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped
            else address
        )
        if (
            not effective_address.is_global
            or effective_address.is_multicast
            or isinstance(effective_address, ipaddress.IPv4Address)
            and effective_address in cls._CGNAT
        ):
            raise MediaImportError(
                MediaImportErrorCode.UNSAFE_URL,
                "URL resolves to a non-public IP address",
                details={"ip": str(address)},
            )
        return str(address)

    @staticmethod
    def _raise(code: MediaImportErrorCode, message: str) -> None:
        raise MediaImportError(code, message)
