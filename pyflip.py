import re
from typing import List
import httpx
import asyncio
import aiofiles
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import shutil
import json
from PIL import Image

SANITISE_PATTERN = re.compile(r"anyflip\.com/([^/]+)/([^/]+)")
DOMAIN_URL = "https://online.anyflip.com"


class Pyflip:
    def __init__(self, full_url: str, configjs: dict) -> None:
        self.url: str = _sanitise_url(full_url)
        self.configjs = configjs
        self.title: str = _get_title(self.configjs)
        self.page_count: int = _get_page_count(self.configjs)
        self.page_urls: List[str] = _get_page_urls(
            self.configjs, self.url, self.page_count
        )

    async def download_pdf(self, client: httpx.AsyncClient) -> None:
        await self.download_images(client)
        self.create_pdf()

    async def download_images(self, client: httpx.AsyncClient) -> None:
        os.makedirs(self.title, exist_ok=True)
        urls = self.page_urls
        extension = os.path.splitext(urls[0])[1]

        # 10 ~ 20 was the best during testing
        sem = asyncio.Semaphore(15)

        async def _dl1(idx: int, url: str):
            async with sem:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.content

                    filename = f"{idx:04d}{extension}"
                    file_path = os.path.join(self.title, filename)

                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(data)

                except Exception as e:
                    raise ValueError(f"[Error] {url}: {e}")

        tasks = [asyncio.create_task(_dl1(i, u)) for i, u in enumerate(urls)]
        await asyncio.gather(*tasks, return_exceptions=True)

    def create_pdf(self) -> None:
        img_dir = self.title
        output_file = self.title + ".pdf"
        image_files = [os.path.join(img_dir, f) for f in os.listdir(img_dir)]

        if not image_files:
            raise FileNotFoundError("No images found")
        else:
            image_files.sort()

        def load_image(path):
            try:
                with Image.open(path) as im:
                    return im.copy()
            except Exception as e:
                raise LookupError(f"Failed to open '{path}': {e}") from e

        # Minimum 8 worker threads
        cpu_count = os.cpu_count() or 4
        max_workers = cpu_count * 2

        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(load_image, p): p for p in image_files}
            for fut in as_completed(futures):
                path = futures[fut]
                results[path] = fut.result()

        # Sort results by filename order
        images = [results[path] for path in image_files]

        try:
            images[0].save(
                output_file,
                "PDF",
                save_all=True,
                append_images=images[1:],
            )
        except Exception as e:
            raise RuntimeError(f"Failed to save PDF: {e}")

        try:
            shutil.rmtree(img_dir)
        except OSError as e:
            raise OSError(f"Failed to remove '{img_dir}': {e}")


def _sanitise_url(full_url: str) -> str:
    match = SANITISE_PATTERN.search(full_url)

    if match:
        return f"/{match.group(1)}/{match.group(2)}/"
    else:
        raise ValueError("Required path elements not found")


async def fetch_configjs(full_url: str, client: httpx.AsyncClient) -> dict:
    url = _sanitise_url(full_url)
    CONFIGJS_PATH = "mobile/javascript/config.js"
    config_js_url = DOMAIN_URL + url + CONFIGJS_PATH
    print(config_js_url)

    try:
        resp = await client.get(config_js_url)
        js_text = resp.text.strip()

        start = js_text.find("{")
        end = js_text.rfind("}") + 1

        if start == -1 or end == 0:
            raise ValueError("Could not find a valid configuration object in config.js")

        obj_str = js_text[start:end]

        try:
            return json.loads(obj_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse config.js: {e}")

    except httpx.RequestError as e:
        raise ValueError(f"Failed to get config.js: {e}")


def _get_title(config_dict: dict) -> str:
    meta = config_dict.get("meta", {})
    title = meta.get("title")

    if not title:
        title = config_dict.get("title")
    
    if not title and "bookConfig" in config_dict:
        bc = config_dict["bookConfig"]
        title = bc.get("bookTitle") if isinstance(bc, dict) else None

    return re.sub(r'[<>:"/\\|?*]', '', str(title)).strip().strip('.')


def _get_page_count(config_dict: dict) -> int:
    count = config_dict.get("totalPageCount") or config_dict.get("pageCount")

    if count is None and "bookConfig" in config_dict:
        book_config = config_dict["bookConfig"]
        if isinstance(book_config, dict):
            count = book_config.get("totalPageCount") or book_config.get("pageCount")

    if count is None:
        pages_list = config_dict.get("fliphtml5_pages", [])
        if pages_list:
            count = len(pages_list)

    if count is None:
        raise ValueError("Page count not found in config data")
    try:
        return int(count)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid page count format: {count}")


def _get_page_urls(config_dict: dict, url: str, page_count: int) -> List[str]:
    urls: List[str] = []
    pages_list = config_dict.get("fliphtml5_pages", [])

    for i in range(page_count):
        download_path = ""
        if i < len(pages_list):
            page_data = pages_list[i]
            raw_filenames = page_data.get("n", [])
            if raw_filenames:
                clean_path = raw_filenames[0].replace("\\", "").replace("../", "")
                download_path = clean_path

        if not download_path:
            download_path = f"files/large/{i + 1}.webp"
        elif "files/large/" not in download_path:
            download_path = f"files/large/{download_path}"

        base = url if url.endswith("/") else url + "/"
        urls.append(DOMAIN_URL + base + download_path)

    return urls
