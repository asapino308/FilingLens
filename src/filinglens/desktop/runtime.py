"""Private, persistent Mac storage shared by the bundled desktop service."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys

from filinglens.config import PROJECT_ROOT


KEYCHAIN_SERVICE = "com.filinglens.ollama-cloud"
KEYCHAIN_ACCOUNT = "FilingLens"
KEYCHAIN_SERVICES = {"ollama_cloud": KEYCHAIN_SERVICE, "openai": "com.filinglens.openai",
                     "anthropic": "com.filinglens.anthropic"}
_ITEM_NOT_FOUND = -25300
_DUPLICATE_ITEM = -25299


def app_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "FilingLens"


def prepare_desktop_environment() -> Path:
    """Start packaged installs without importing source settings or research."""
    if not getattr(sys, "frozen", False):
        return PROJECT_ROOT / ".env"
    support = app_data_dir()
    support.mkdir(parents=True, exist_ok=True, mode=0o700)
    support.chmod(0o700)
    environment = support / ".env"
    if environment.exists():
        environment.chmod(0o600)
    cache = support / "cache"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache.chmod(0o700)
    os.environ["FILINGLENS_ENV_FILE"] = str(environment)
    os.environ["FILINGLENS_CACHE_DIR"] = str(cache)
    return environment


def _keychain() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    if sys.platform != "darwin":
        raise RuntimeError("Secure key storage currently requires macOS.")
    security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
    core = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ptr = ctypes.c_void_p
    size = ctypes.c_uint32
    chars = ctypes.c_char_p
    security.SecKeychainFindGenericPassword.argtypes = [ptr, size, chars, size, chars,
                                                        ctypes.POINTER(size), ctypes.POINTER(ptr), ctypes.POINTER(ptr)]
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainAddGenericPassword.argtypes = [ptr, size, chars, size, chars, size, chars, ctypes.POINTER(ptr)]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyAttributesAndData.argtypes = [ptr, ptr, size, chars]
    security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    security.SecKeychainItemDelete.argtypes = [ptr]
    security.SecKeychainItemDelete.restype = ctypes.c_int32
    security.SecKeychainItemFreeContent.argtypes = [ptr, ptr]
    security.SecKeychainItemFreeContent.restype = ctypes.c_int32
    core.CFRelease.argtypes = [ptr]
    core.CFRelease.restype = None
    return security, core


def _find_item(provider: str, *, read_secret: bool) -> tuple[int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]:
    security, _ = _keychain()
    service = KEYCHAIN_SERVICES[provider].encode("utf-8")
    account = KEYCHAIN_ACCOUNT.encode("utf-8")
    length = ctypes.c_uint32()
    secret = ctypes.c_void_p()
    item = ctypes.c_void_p()
    status = security.SecKeychainFindGenericPassword(
        None, len(service), service, len(account), account,
        ctypes.byref(length) if read_secret else None,
        ctypes.byref(secret) if read_secret else None,
        ctypes.byref(item),
    )
    return status, item, length, secret


def read_cloud_key() -> str:
    return read_api_key("ollama_cloud")


def read_api_key(provider: str) -> str:
    if sys.platform != "darwin":
        return ""
    security, core = _keychain()
    status, item, length, secret = _find_item(provider, read_secret=True)
    if status == _ITEM_NOT_FOUND:
        return ""
    if status != 0:
        raise RuntimeError("macOS Keychain could not read the API key.")
    try:
        return ctypes.string_at(secret, length.value).decode("utf-8")
    finally:
        security.SecKeychainItemFreeContent(None, secret)
        if item:
            core.CFRelease(item)


def save_cloud_key(value: str) -> None:
    save_api_key("ollama_cloud", value)


def save_api_key(provider: str, value: str) -> None:
    security, core = _keychain()
    if not value.strip() or "\n" in value or "\r" in value:
        raise ValueError("Enter a valid API key.")
    service = KEYCHAIN_SERVICES[provider].encode("utf-8")
    account = KEYCHAIN_ACCOUNT.encode("utf-8")
    secret = value.strip().encode("utf-8")
    status = security.SecKeychainAddGenericPassword(
        None, len(service), service, len(account), account,
        len(secret), secret, None,
    )
    if status == _DUPLICATE_ITEM:
        found, item, _, _ = _find_item(provider, read_secret=False)
        if found != 0:
            raise RuntimeError("macOS Keychain could not update the API key.")
        try:
            status = security.SecKeychainItemModifyAttributesAndData(item, None, len(secret), secret)
        finally:
            core.CFRelease(item)
    if status != 0:
        raise RuntimeError("macOS Keychain could not save the API key.")


def delete_cloud_key() -> None:
    delete_api_key("ollama_cloud")


def delete_api_key(provider: str) -> None:
    if sys.platform != "darwin":
        return
    security, core = _keychain()
    status, item, _, _ = _find_item(provider, read_secret=False)
    if status == _ITEM_NOT_FOUND:
        return
    if status != 0:
        raise RuntimeError("macOS Keychain could not remove the API key.")
    try:
        if security.SecKeychainItemDelete(item) != 0:
            raise RuntimeError("macOS Keychain could not remove the API key.")
    finally:
        core.CFRelease(item)
