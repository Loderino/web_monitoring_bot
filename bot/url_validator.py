import ipaddress
import re
from urllib.parse import urlparse


class URLValidator:
    forbidden_ip_ranges = [
        ipaddress.IPv4Network("127.0.0.0/8"),  # Loopback
        ipaddress.IPv4Network("10.0.0.0/8"),  # Private Class A
        ipaddress.IPv4Network("172.16.0.0/12"),  # Private Class B
        ipaddress.IPv4Network("192.168.0.0/16"),  # Private Class C
        ipaddress.IPv4Network("169.254.0.0/16"),  # Link-local
        ipaddress.IPv4Network("224.0.0.0/4"),  # Multicast
        ipaddress.IPv4Network("240.0.0.0/4"),  # Reserved
        ipaddress.IPv6Network("::1/128"),  # IPv6 loopback
        ipaddress.IPv6Network("fc00::/7"),  # IPv6 private
        ipaddress.IPv6Network("fe80::/10"),  # IPv6 link-local
    ]

    forbidden_domains = {
        "localhost",
        "localhost.localdomain",
        "0.0.0.0",
        "broadcasthost",
    }

    forbidden_domain_patterns = [
        r".*\.local$",  # .local домены
        r".*\.localhost$",  # .localhost домены
        r".*\.internal$",  # .internal домены
        r".*\.corp$",  # .corp домены
        r".*\.lan$",  # .lan домены
        r".*\.intranet$",  # .intranet домены
    ]

    allowed_schemes = {"http", "https"}

    forbidden_ports = {
        22,  # SSH
        23,  # Telnet
        25,  # SMTP
        53,  # DNS
        110,  # POP3
        143,  # IMAP
        993,  # IMAPS
        995,  # POP3S
        1433,  # MSSQL
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        27017,  # MongoDB
    }

    max_url_length = 2048


    def validate_url(self, url: str) -> tuple[bool, str]:
        """
        Основная функция валидации URL

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            if not url or not isinstance(url, str):
                return False, "URL не может быть пустым"

            if len(url) > self.max_url_length:
                return (
                    False,
                    f"URL слишком длинный (максимум {self.max_url_length} символов)",
                )

            try:
                parsed = urlparse(url.lower().strip())
            except Exception:
                return False, "Некорректный формат URL"

            if parsed.scheme not in self.allowed_schemes:
                return (
                    False,
                    f"Разрешены только схемы: {', '.join(self.allowed_schemes)}",
                )

            if not parsed.hostname:
                return False, "URL должен содержать имя хоста"

            if parsed.port and parsed.port in self.forbidden_ports:
                return False, f"Порт {parsed.port} запрещен"

            domain_valid, domain_error = self._validate_domain(parsed.hostname)
            if not domain_valid:
                return False, domain_error

            suspicious_valid, suspicious_error = self._check_suspicious_patterns(url)
            if not suspicious_valid:
                return False, suspicious_error

            return True, "URL корректен"

        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}"

    def _validate_domain(self, hostname: str) -> tuple[bool, str]:
        """Валидация домена или IP адреса"""
        if hostname.lower() in self.forbidden_domains:
            return False, f"Домен '{hostname}' запрещен"

        for pattern in self.forbidden_domain_patterns:
            if re.match(pattern, hostname.lower()):
                return False, f"Домен '{hostname}' соответствует запрещенному паттерну"

        try:
            ip = ipaddress.ip_address(hostname)
            return self._validate_ip_address(ip)
        except ValueError:
            return self._validate_domain_name(hostname)

    def _validate_ip_address(
        self, ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> tuple[bool, str]:
        """Валидация IP адреса"""
        for forbidden_range in self.forbidden_ip_ranges:
            if ip in forbidden_range:
                return (
                    False,
                    f"IP адрес {ip} находится в запрещенном диапазоне ({forbidden_range})",
                )

        if isinstance(ip, ipaddress.IPv4Address):
            if ip.is_multicast:
                return False, f"Multicast адрес {ip} запрещен"

            if ip.is_reserved:
                return False, f"Зарезервированный адрес {ip} запрещен"

        return True, "IP адрес корректен"

    def _validate_domain_name(self, domain: str) -> tuple[bool, str]:
        """Валидация доменного имени"""
        if len(domain) > 253:
            return False, "Доменное имя слишком длинное"

        if domain.startswith("-") or domain.endswith("-"):
            return False, "Доменное имя не может начинаться или заканчиваться дефисом"

        domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
        if not re.match(domain_pattern, domain):
            return False, "Некорректный формат доменного имени"

        parts = domain.split(".")
        if len(parts) < 2:
            return False, "Домен должен содержать домен верхнего уровня"

        for part in parts:
            if len(part) > 63:
                return False, "Часть доменного имени не может быть длиннее 63 символов"

        return True, "Доменное имя корректно"

    def _check_suspicious_patterns(self, url: str) -> tuple[bool, str]:
        """Проверка на подозрительные паттерны в URL"""
        suspicious_patterns = [
            r".*@.*",  # Наличие @ (возможная попытка обхода)
            r".*\.\./.*",  # Directory traversal
            r'.*[<>"\'].*',  # Потенциальные XSS символы
            r".*file://.*",  # File protocol
            r".*ftp://.*",  # FTP protocol
            r".*javascript:.*",  # JavaScript protocol
            r".*data:.*",  # Data protocol
        ]

        for pattern in suspicious_patterns:
            if re.match(pattern, url.lower()):
                return False, "URL содержит подозрительные элементы"

        return True, "URL не содержит подозрительных паттернов"
