# anyflip-dl

A GUI app to download anyflip books as PDFs.

⚠️ **Critial bug stopping some downloads: [Details](https://github.com/AlimulK/anyflip-dl/issues/12)** ⚠️

## Install

Download the most recent version for your platform: [Releases](https://github.com/AlimulK/pyflip-dl/releases).

## How to use?

### Windows and Linux

1. Launch the app
2. Paste in the URL of the PDF you want
3. Press Download and wait until the bar stops moving
4. Profit

### MacOS

According to Apple's [advice](https://support.apple.com/en-gb/guide/mac-help/mh40616/mac)

1. Locate the app in Finder
(don’t use Launchpad to do this. Launchpad doesn’t allow you to access the shortcut menu)
2. Control-click the app icon, then choose Open from the shortcut menu
3. Click Open (you can open it in the future by double-clicking it)
4. Paste in the URL of the PDF you want
5. Press Download and wait until the bar stops moving
6. Profit

### Errors

If there was an error during download the app will let you know.
You can still download the book by toggling `Download Incomplete Books`.
This will simply skip the pages causing errors on creating the PDF.

## Developers

> Python 3.13

Set up your virtual environment as you usually do and install the dependencies:

```bash
pip install -r requirements.txt
```

## Disclaimer

Only use this tool to download books that officially allow PDFs to be downloaded.

## Credits

Inspired by and extends [anyflip-downloader](https://github.com/Lofter1/anyflip-downloader).
