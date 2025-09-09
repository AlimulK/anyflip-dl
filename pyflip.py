import os
import re
import shutil
from typing import List

import requests
from PIL import Image

from errors import (
    PyflipError,
    URLSanitizationError,
    DownloadError,
    ParseError,
    FileSystemError,
    PDFCreationError,
)


class Flipbook:
    """This represents a PDF book object from anyflip."""

    def __init__(self, url: str, title: str, page_count: int, page_urls: List[str]):
        self.url: str = url
        self.title: str = title
        self.page_count: int = page_count
        self.page_urls: List[str] = page_urls


class ConfigJs:
    """A bunch of regex helper functions for configjs."""

    @staticmethod
    def get_page_filenames(configjs: str) -> List[str]:
        pattern = re.compile(r'"n":\[".*?"]')
        matches = pattern.findall(configjs)

        for i, match in enumerate(matches):
            # Remove the part before and including the colon
            match = match.split(":")[1]
            # Remove the square brackets and double quotes
            match = match.replace("[", "").replace("]", "").replace("\"", "")
            matches[i] = match

        return matches

    @staticmethod
    def get_book_title(configjs: str) -> str:
        pattern = re.compile(r'("?(bookConfig\.)?bookTitle"?[=]"(.*?)")|"title":"(.*?)"')
        match = pattern.search(configjs)

        if not match:
            return ""

        match = match.group(0)

        if "=" in match:
            match = match.split("=")[1]
        elif ":" in match:
            match = match.split(":")[1]
        else:
            return ""

        match = match.replace("\"", "")

        return match

    @staticmethod
    def get_page_count(configjs: str) -> int:
        pattern = re.compile(r'"?(bookConfig\.)?(total)?[Pp]ageCount"?[=:]"?\d+"?')
        match = pattern.search(configjs)

        if not match:
            raise ParseError("Could not find page count in config.js")

        match = match.group(0)

        if "=" in match:
            match = match.split("=")[1]
        elif ":" in match:
            match = match.split(":")[1]
        else:
            raise ParseError("Unexpected page count format in config.js")

        match = match.replace("\"", "")

        try:
            return int(match)
        except ValueError as exc:
            raise ParseError("Invalid page count value in config.js") from exc


class Pyflip:
    """This contains most of the important logic."""

    @staticmethod
    def sanitize_url(anyflip_url: str) -> str:
        """This returns a str with the important part of the URL (/xxxxx/xxxx/)."""
        match = re.search(r'anyflip\.com/([^/]+)/([^/]+)', anyflip_url)
        if match:
            return f'/{match.group(1)}/{match.group(2)}/'
        else:
            raise URLSanitizationError("The URL does not contain the required path elements")

    @staticmethod
    def download_config_js_file(anyflip_url: str) -> str:
        base_url = "https://online.anyflip.com"
        config_js_path = "mobile/javascript/config.js"
        config_js_url = base_url + anyflip_url + config_js_path

        try:
            response = requests.get(config_js_url)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DownloadError(f"Failed to download config.js: {exc}") from exc

        return response.text

    @staticmethod
    def prepare_download(anyflip_url: str) -> Flipbook:
        """Create a `Flipbook` object for download

        Implicitly requires `sanitize_url` since `anyflip_url`
        needs to be a sanitized url.
        """
        anyflip_url = Pyflip.sanitize_url(anyflip_url)
        config_js = Pyflip.download_config_js_file(anyflip_url)

        title = ConfigJs.get_book_title(config_js)
        if not title:
            title = anyflip_url

        page_count = ConfigJs.get_page_count(config_js)
        page_file_names = ConfigJs.get_page_filenames(config_js)

        new_flipbook = Flipbook(url=anyflip_url, title=title, page_count=page_count, page_urls=[])

        base_url = "https://online.anyflip.com"

        for i in range(page_count):
            # Check that config.js has this page
            if i < len(page_file_names):
                download_path = anyflip_url + "files/large/" + page_file_names[i]
            # Else fallback on numbers
            else:
                download_path = anyflip_url + "files/large/" + f"{i + 1}.jpg"
            
            download_url = base_url + download_path
            new_flipbook.page_urls.append(download_url)

        return new_flipbook

    @staticmethod
    def download_images(download_folder: str, flipbook: Flipbook, allow_incomplete: bool = False) -> tuple[int, int]:
        """Downloads the PDF as a series of images."""
        try:
            # Make the folder
            os.makedirs(download_folder, exist_ok=True)
        except Exception as exc:
            raise FileSystemError(f"Failed to create folder '{download_folder}': {exc}") from exc

        downloaded = 0
        skipped = 0

        # Downloads the PDF page by page
        for page in range(flipbook.page_count):
            download_url = flipbook.page_urls[page]
            try:
                response = requests.get(download_url)
            except requests.RequestException as exc:
                if allow_incomplete:
                    skipped += 1
                    continue
                raise DownloadError(f"Failed to download page {page + 1} from {download_url}: {exc}") from exc

            if response.status_code != 200:
                if allow_incomplete:
                    skipped += 1
                    continue
                raise DownloadError(
                    f"Download returned status {response.status_code} for page {page + 1}: {download_url}"
                )

            extension = os.path.splitext(download_url)[1]
            filename = f"{page:04d}{extension}"
            file_path = os.path.join(download_folder, filename)

            try:
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                downloaded += 1
            except Exception as exc:
                if allow_incomplete:
                    skipped += 1
                    continue
                raise FileSystemError(f"Failed to write image '{file_path}': {exc}") from exc

        return downloaded, skipped

    @staticmethod
    def create_pdf(
        output_file: str,
        img_dir: str,
        keep_folder: bool = False,
        allow_incomplete: bool = False,
    ) -> None:
        """Create a PDF from images in `img_dir`."""
        # Sanitize output_file
        output_file = output_file.replace("'", "").replace("\\", "").replace(":", "")
        output_file = output_file + ".pdf"

        # Get a list of all image files in the specified folder
        image_files = [os.path.join(img_dir, f) for f in os.listdir(img_dir)]

        image_files.sort()

        images = []
        for img_file in image_files:
            try:
                with Image.open(img_file) as im:
                    if im.mode == "RGB":
                        images.append(im.copy())
                    else:
                        images.append(im.convert("RGB"))
            except Exception as exc:
                if allow_incomplete:
                    # Skip unreadable/corrupt images when allowed
                    continue
                raise PDFCreationError(
                    f"Failed to open image '{img_file}': {exc}"
                ) from exc

        # Save the images as a single PDF file
        if images:
            try:
                images[0].save(
                    output_file, "PDF", resolution=100.0, save_all=True, append_images=images[1:]
                )
            except Exception as exc:
                raise PDFCreationError(f"Failed to save PDF '{output_file}': {exc}") from exc
        else:
            raise PDFCreationError("No valid images found to create the PDF.")

        # If the keep folder option isn't checked then folder is deleted
        if not keep_folder:
            try:
                shutil.rmtree(img_dir)
            except Exception as exc:
                raise FileSystemError(f"Failed to remove folder '{img_dir}': {exc}") from exc
