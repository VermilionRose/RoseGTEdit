"""
vMix Web API client.
Discovers GT Title inputs currently loaded in vMix.
"""

import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional


VMIX_API_URL = "http://localhost:8088/api/"


@dataclass
class VMixTitle:
    number: str
    title: str
    filepath: str   # local path to .gtzip or .gtxml


def fetch_titles(host: str = "localhost", port: int = 8088, timeout: float = 3.0) -> list[VMixTitle]:
    """
    Query vMix API and return all GT Title inputs.
    Raises requests.RequestException on connection failure.
    """
    url = f"http://{host}:{port}/api/"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    titles = []

    for inp in root.iter("input"):
        inp_type = inp.get("type", "")
        if inp_type.upper() != "GT":
            continue

        number = inp.get("number", "")
        title = inp.get("title", inp.get("shortTitle", ""))

        # Try multiple attribute names for the file path
        filepath = (
            inp.get("filename")
            or inp.get("location")
            or inp.get("videoFilename")
            or ""
        )

        # Also try inner text of <location> child
        if not filepath:
            loc = inp.find("location")
            if loc is not None and loc.text:
                filepath = loc.text.strip()

        if filepath:
            titles.append(VMixTitle(number=number, title=title, filepath=filepath))

    return titles


def check_connection(host: str = "localhost", port: int = 8088) -> bool:
    try:
        requests.get(f"http://{host}:{port}/api/", timeout=2.0)
        return True
    except Exception:
        return False
