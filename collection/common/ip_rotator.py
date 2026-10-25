# -*- coding: utf-8 -*-
"""Bộ quản lý và xoay vòng Proxy / Fake IP (In-Browser Proxy Rotator) cho VN-IT-Job-Mining.

Hỗ trợ:
1. Xoay danh sách proxy từ file (proxies.txt) theo vòng tròn (Round-Robin) hoặc ngẫu nhiên.
2. Hỗ trợ Single Rotating Proxy Gateway (BrightData, Smartproxy, IPRoyal, Webshare, v.v.).
3. Tự động chuẩn hóa các định dạng proxy phổ biến:
   - ip:port
   - ip:port:username:password
   - http://username:password@ip:port
   - socks5://username:password@ip:port
4. Kiểm tra sức khỏe proxy (Health Check) và lấy địa chỉ IP công khai thực tế.
"""

from __future__ import annotations

import logging
import os
import random
import re
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests

log = logging.getLogger("ip_rotator")


def normalize_proxy_url(raw: str) -> Optional[str]:
    """Chuẩn hóa chuỗi proxy về định dạng URL chuẩn http://[user:pass@]host:port."""
    s = raw.strip()
    if not s or s.startswith("#"):
        return None

    # Nếu đã có scheme (http://, https://, socks5://)
    if s.startswith(("http://", "https://", "socks5://", "socks4://")):
        return s

    # Dạng ip:port:user:pass
    parts = s.split(":")
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return f"http://{user}:{pwd}@{ip}:{port}"

    # Dạng user:pass@ip:port
    if "@" in s:
        return f"http://{s}"

    # Dạng ip:port
    if len(parts) == 2:
        return f"http://{s}"

    return f"http://{s}"


def check_proxy_ip(proxy_url: str, timeout: float = 6.0) -> Optional[str]:
    """Kiểm tra proxy hoạt động và trả về IP công khai thực tế."""
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        resp = requests.get(
            "https://api.ipify.org?format=json",
            proxies=proxies,
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json().get("ip")
    except Exception as exc:
        log.debug("Proxy %s lỗi kết nối: %s", proxy_url, exc)
    return None


class ProxyPool:
    """Quản lý danh sách proxy xoay vòng cho crawler."""

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        proxy_file: Optional[str] = None,
        random_choice: bool = False,
    ) -> None:
        self.proxies: List[str] = []
        self.current_index = 0
        self.random_choice = random_choice
        self.single_rotating_url = None

        if proxy_url:
            norm = normalize_proxy_url(proxy_url)
            if norm:
                self.single_rotating_url = norm
                self.proxies.append(norm)

        if proxy_file:
            path = Path(proxy_file)
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    norm = normalize_proxy_url(line)
                    if norm and norm not in self.proxies:
                        self.proxies.append(norm)

        log.info("Khởi tạo ProxyPool với %d proxy hợp lệ.", len(self.proxies))

    def has_proxies(self) -> bool:
        return len(self.proxies) > 0

    def get_current(self) -> Optional[str]:
        if not self.proxies:
            return None
        return self.proxies[self.current_index % len(self.proxies)]

    def rotate(self) -> Optional[str]:
        """Chuyển sang proxy tiếp theo trong danh sách."""
        if not self.proxies:
            return None

        # Nếu là 1 single rotating gateway (ví dụ proxy xoay tự động mỗi request)
        if self.single_rotating_url and len(self.proxies) == 1:
            log.info("[ProxyPool] Sử dụng Single Rotating Gateway (IP tự đổi từ nhà cung cấp): %s", self.single_rotating_url)
            return self.single_rotating_url

        if self.random_choice:
            self.current_index = random.randint(0, len(self.proxies) - 1)
        else:
            self.current_index = (self.current_index + 1) % len(self.proxies)

        next_proxy = self.proxies[self.current_index]
        log.info(
            "[ProxyPool] Đã xoay sang proxy [%d/%d]: %s",
            self.current_index + 1,
            len(self.proxies),
            next_proxy.split("@")[-1] if "@" in next_proxy else next_proxy,
        )
        return next_proxy
