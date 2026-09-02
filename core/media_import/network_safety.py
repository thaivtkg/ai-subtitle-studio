import ipaddress
import socket
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
