import os
import re
import shutil

import requests
from PIL import Image


class Flipbook:
    """This represents a PDF book object from anyflip."""

    def __init__(self, url, title, page_count, page_urls):
        self.url: str = url
        self.title: str = title
        self.page_count: int = page_count
        self.page_urls: list[str] = page_urls


class ConfigJs:
    """A bunch of regex helper functions for configjs."""

    def get_page_filenames(configjs: str) -> list[str]:
        pattern = re.compile(r'"n":\[".*?"]')
        matches = pattern.findall(configjs)

        for i, match in enumerate(matches):
            # Remove the part before and including the colon
            match = match.split(":")[1]
            # Remove the square brackets and double quotes
            match = match.replace("[", "").replace("]", "").replace("\"", "")
            matches[i] = match

        return matches

    def get_book_title(configjs: str) -> str:
        pattern = re.compile(r'("?(bookConfig\.)?bookTitle"?[=]"(.*?)")|"title":"(.*?)"')
        match = pattern.search(configjs)

        if not match:
            return "could not find book title"

        match = match.group(0)

        if "=" in match:
            match = match.split("=")[1]
        elif ":" in match:
            match = match.split(":")[1]
        else:
            return "could not find book title"

        match = match.replace("\"", "")

        return match

    def get_page_count(configjs: str) -> int:
        pattern = re.compile(r'"?(bookConfig\.)?(total)?[Pp]ageCount"?[=:]"?\d+"?')
        match = pattern.search(configjs)

        if not match:
            return 0

        match = match.group(0)

        if "=" in match:
            match = match.split("=")[1]
        elif ":" in match:
            match = match.split(":")[1]
        else:
            return 0

        match = match.replace("\"", "")

        try:
            return int(match)
        except ValueError:
            return 0


class Pyflip:
    """This contains most of the important logic."""

    def sanitize_url(anyflip_url: str) -> str:
        """This returns a str with the important part of the URL (/xxxxx/xxxx/)."""
        match = re.search(r'anyflip\.com/([^/]+)/([^/]+)', anyflip_url)
        if match:
            return f'/{match.group(1)}/{match.group(2)}/'
        else:
            raise ValueError("The URL does not contain the required path elements")

    def download_config_js_file(anyflip_url: str) -> str:
        try:
            base_url = "https://online.anyflip.com"
            config_js_path = "mobile/javascript/config.js"
            config_js_url = base_url + anyflip_url + config_js_path

            response = requests.get(config_js_url)
            response.raise_for_status()

            return response.text
        except requests.RequestException as e:
            return f"An error occurred: {e}"

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

        if not page_file_names:
            for i in range(1, page_count + 1):
                download_path = anyflip_url + "files/mobile/" + f"{i}.jpg"
                download_url = base_url + download_path
                new_flipbook.page_urls.append(download_url)
        else:
            for i in range(page_count):
                download_path = anyflip_url + "files/large/" + page_file_names[i]
                download_url = base_url + download_path
                new_flipbook.page_urls.append(download_url)

        return new_flipbook

    def download_images(download_folder: str, flipbook: Flipbook):
        """Downloads the PDF as a series of images"""
        try:
            # Make the folder
            os.makedirs(download_folder, exist_ok=True)
        except Exception as e:
            return str(e)

        # Downloads the PDF page by page
        for page in range(flipbook.page_count):
            download_url = flipbook.page_urls[page]
            response = requests.get(download_url)

            if response.status_code != 200:
                print(f"During download from {download_url} received {response.status_code}")

            extension = os.path.splitext(download_url)[1]
            filename = f"{page:04d}{extension}"
            file_path = os.path.join(download_folder, filename)

            try:
                with open(file_path, 'wb') as file:
                    file.write(response.content)
            except Exception as e:
                print(str(e))

    def create_pdf(output_file: str, img_dir: str, del_folder: bool = True):
        """Put the images together in an array and then turn it into a PDF."""
        # Sanitize output_file
        output_file = output_file.replace("'", "").replace("\\", "").replace(":", "")
        output_file = output_file + ".pdf"

        # Get a list of all image files in the specified folder
        image_files = [
            os.path.join(img_dir, f)
            for f in os.listdir(img_dir)
        ]

        image_files.sort()

        images = [Image.open(img_file) for img_file in image_files]

        # Save the images as a single PDF file
        if images:
            images[0].save(
                output_file, "PDF", resolution=100.0, save_all=True, append_images=images[1:]
            )
        else:
            print("No images found in the specified folder.")

        if del_folder:
            try:
                shutil.rmtree(img_dir)
            except Exception as e:
                print(str(e))
