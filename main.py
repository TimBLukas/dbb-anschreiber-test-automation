"""Extract DBB quiz questions (Kampfrichterkurs) and compare them with a local study catalogue.

The script supports two input workflows:

* ``--manual`` reads a locally saved ``test.html`` file.
* ``--automated`` obtains the current quiz page through the supported
  browser-integration workflow.

Questions are extracted from the HTML code of the quiz, normalized, and matched
approximately against the questions in ``questions.json`` using fuzzy string
matching.
The program prints the closest catalogue answer and explanation; it
does not verify matches, submit answers, or modify a website.

This is an unofficial study aid. Catalogue entries and matches may be
incomplete, outdated, or incorrect, so verify the output against current
official materials.

Use the script only with content you are authorized to
access and in accordance with the applicable assessment rules and terms of
use.

It must not be used to bypass an examination, certification, or training
requirement, the author does not take responsibility for your usage of this code!


:author: TBL
:version: 0.1.0
"""

import argparse
import asyncio

from bs4 import BeautifulSoup

from dataclasses import dataclass

import json

from pathlib import Path
from playwright.async_api import async_playwright

from rapidfuzz.fuzz import ratio
import re

import shutil
import socket
import subprocess
from sys import platform

import tempfile
from textwrap import fill
import time
from typing import Optional, Sequence


APP_VERSION = "0.1.0"
DEFAULT_CATALOGUE = Path(__file__).with_name("questions.json")


@dataclass
class QCatalogue:
    id: Optional[str]
    question: Optional[str]
    answer: Optional[str]
    article: Optional[str]
    explanation: Optional[str]

@dataclass
class QMatch:
    question: str
    solution: QCatalogue | None

def _load_question_catalogue(path: Path) -> list[QCatalogue]:
    with path.open(encoding="utf-8") as f:
        questions = json.load(f)
    return [QCatalogue(
        q.get("id"),
        q.get("question"),
        q.get("answer"),
        q.get("article"),
        q.get("explanation")
    ) for q in questions]
def normalize(s: str):
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()

def _string_similarity(s1: str, s2: str):
    return ratio(normalize(s1), normalize(s2))

def find_best_match(question: str, answers: list[QCatalogue]) -> QMatch:
    best_match: Optional[QCatalogue] = None 
    best_score: float = 0
    for solution in answers:
        score = _string_similarity(question, solution.question)
        if score > best_score:
            best_match = solution
            best_score = score
    return QMatch(question, best_match)

def _fetch_test_html_macos():
    print(
        "\n"
        "1. Open Safari, go to the DBB site and login (url: https://dbb.triagonal.net/online/course/view.php?id=18) \n2. Select the test\n3. Start the test\n"
    )

    input("Press ENTER once the test has started...")

    script = '''
        tell application "Safari"
            tell current tab of window 1
                do JavaScript "document.documentElement.outerHTML"
            end tell
        end tell
    '''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    html = result.stdout
    return html

def _find_chrome() -> str:
    if platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif platform == "win32":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
        ]

    elif platform == "linux" or platform == "linux2":
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]

    else:
        raise RuntimeError(f"Unsupported operating system: {platform}")

    for path in candidates:
        if Path(path).is_file():
            return path

    for exe in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        chrome_path = shutil.which(exe)
        if chrome_path:
            return chrome_path

    raise FileNotFoundError("Could not find a Chrome/Chromium installation.")
        

def _launch_chrome_in_debugging_mode(
        port: int = 9222, 
        url: str | None = "https://dbb.triagonal.net/online/course/view.php?id=18"
    ) -> subprocess.Popen:
    chrome_path = _find_chrome()
    user_data_dir = tempfile.mkdtemp(prefix="chrome-debug-")

    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
    ]
    if url:
        args.append(url)
    process = subprocess.Popen(args=args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time_limit = time.time() + 10

    while time.time() < time_limit:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return process
        time.sleep(0.5)
    process.terminate()
    raise RuntimeError(f"Chrome did not start the remote debugging server on port {port}")

    

async def _fetch_test_html_chrome() -> str | None:
    _launch_chrome_in_debugging_mode()
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(
            "http://localhost:9222"
        )
        print(
            "\n"
            "1. Log in to your DBB account\n2. Select the test\n3. Start the test\n"
        )

        await asyncio.to_thread(
            input,
            "Press ENTER once the test has started..."
        )

        context = browser.contexts[0]

        for page in context.pages:
            if "dbb.triagonal" in page.url:
                return await page.content()
    return None

def _fetch_test_html() -> str | None:
    match platform:
        case "linux":
            return asyncio.run(_fetch_test_html_chrome())
        case "linux2":
            return asyncio.run(_fetch_test_html_chrome())
        case "win32":
            return asyncio.run(_fetch_test_html_chrome())
        case "darwin":
            return _fetch_test_html_macos()

    raise RuntimeError("Unable to identify OS to fetch Test HTML")

def _extract_questions(html: str) -> list[str]:
    """Extract the question text from the dbb html quiz content page"""
    soup = BeautifulSoup(html, "html.parser")
    page_div = soup.find("div", id="page")
    if page_div is None:
        raise ValueError("Could not find the quiz page container (div#page)")

    questions = []
    for question_text in page_div.select("div.que div.qtext"):
        text = question_text.get_text(" ", strip=True)
        if text:
            questions.append(text)

    return questions

def _output_solution(answers: list[QMatch]):
    """Print matched answers in a readable terminal-friendly format."""
    width = 72
    separator = "=" * width

    print(f"\n{separator}")
    print("Generated Answers".center(width))
    print(separator)

    for index, match in enumerate(answers, start=1):
        print(f"\n{index:>2}. Question")
        print(fill(match.question, width=width - 4, initial_indent="    ",
                   subsequent_indent="    "))
        if match.solution is None:
            print("    Answer: No catalogue match found")
            continue

        print(f"    Answer: {match.solution.answer or 'Unknown'}")

        if match.solution.explanation:
            print(fill(
                f"Explanation: {match.solution.explanation}",
                width=width - 4,
                initial_indent="    ",
                subsequent_indent="               ",
            ))

    print(f"\n{separator}")


def _get_argparser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="anschreiber-helper",
        description=(
            "Extract questions from an authorized, locally saved DBB quiz page "
            "and compare them with the local study catalogue.\n\n"
            "The input page can be prepared manually or obtained through the "
            "supported browser-integration workflow. The tool only displays "
            "approximate catalogue matches; it does not verify answers or "
            "submit anything to a website."
        ),
        epilog=(
            "Responsible use: only process pages and question catalogues that "
            "you are authorized to access. Do not use this tool to bypass an "
            "examination, certification requirement, authentication control, "
            "or assessment rule. Review every match against current official "
            "materials. The output is an unofficial study aid and may be "
            "incomplete or incorrect."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--manual",
        action="store_true",
        help="Read a local HTML file (default when choosing interactively)",
    )
    mode.add_argument(
        "--automated",
        action="store_true",
        help="Open the browser workflow and read the current quiz page",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("test.html"),
        metavar="PATH",
        help="HTML file to read with --manual (default: test.html)",
    )
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=DEFAULT_CATALOGUE,
        metavar="PATH",
        help=f"Question catalogue (default: {DEFAULT_CATALOGUE.name})",
    )
    return parser

def _parse_and_output(html: str | None, catalogue_path: Path) -> None:
    if not html:
        raise ValueError("No quiz HTML was received.")

    questions = _extract_questions(html)
    if not questions:
        raise ValueError("No questions were found in the supplied quiz HTML.")

    try:
        catalogue = _load_question_catalogue(catalogue_path)
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Question catalogue not found: {catalogue_path}\n"
            "Pass its location with --catalogue."
        ) from error
    _output_solution([find_best_match(question, catalogue) for question in questions])

def manual(html_path: Path, catalogue_path: Path) -> None:
    try:
        content = html_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"HTML file not found: {html_path}\n"
            "Create it first or pass a different path with --html."
        ) from error
    _parse_and_output(content, catalogue_path)

def automatic(catalogue_path: Path) -> None:
    html = _fetch_test_html()
    _parse_and_output(html, catalogue_path)

def _choose_mode() -> str:
    print("\nHow would you like to provide the quiz HTML?")
    print("  1. Use a local test.html file")
    print("  2. Open the browser workflow")
    while True:
        choice = input("Choose 1 or 2 [1]: ").strip() or "1"
        if choice in {"1", "2"}:
            return choice
        print("Please enter 1 or 2.")

def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit status."""
    parser = _get_argparser()
    args = parser.parse_args(argv)

    try:
        if args.manual or (not args.manual and not args.automated and _choose_mode() == "1"):
            manual(args.html, args.catalogue)
        else:
            automatic(args.catalogue)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))

    return 0

    

if __name__ == "__main__":
    SystemExit(main())
