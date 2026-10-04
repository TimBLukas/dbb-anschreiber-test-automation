"""
This is a helper to pass the Anschreiber Test from DBB

I do not take responsibility for using this tool, it is entirely your responsibility if you want to cheat or not!
The solutions are based on the "fragenkatalog" published online, answers are not guaranteed to be correct
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
from typing import Optional


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

def _load_question_catalogue():
    with open("questions.json", "r") as f:
        questions = json.load(f)
    return [QCatalogue(
        q.get("id"),
        q.get("question"),
        q.get("answer"),
        q.get("article"),
        q.get("explanation")
    ) for q in questions]
ANSWERS = _load_question_catalogue()

def normalize(s: str):
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()

def _string_similarity(s1: str, s2: str):
    return ratio(normalize(s1), normalize(s2))

def find_best_match(question: str) -> QMatch:
    best_match: Optional[QCatalogue] = None 
    best_score: float = 0
    for solution in ANSWERS:
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

def _load_answer(question: str) -> QMatch:
    return find_best_match(question)

def _load_answers(questions: list[str]) -> list[QMatch]:
    return [_load_answer(q) for q in questions]


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
        version="%(prog)s 0.1",
    )
    parser.add_argument("--manual", action="store_true", help="Use this option if you want to manually copy the sites html to the test.html file")
    parser.add_argument("--automated", action="store_true", help="Use this option if you want to have the script automatically use the html of the currently open browser window")
    return parser

def _parse_and_output(html: str) -> None:
    questions = _extract_questions(html) if html else None
    answers = _load_answers(questions)
    _output_solution(answers)

def manual():
    with open("test.html", "r") as f:
        content = f.read()
    _parse_and_output(content)

def automatic():
    html = _fetch_test_html()
    _parse_and_output(html)

def main():
    parser = _get_argparser()
    args = parser.parse_args()

    if args.manual:
        manual()
    elif args.automated:
        automatic()
    else:
        raise RuntimeError("The option provided was not recognized, try --help")

    return 0

    

if __name__ == "__main__":
    SystemExit(main())
