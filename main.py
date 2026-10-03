"""
This is a helper to pass the Anschreiber Test from DBB

I do not take responsibility for using this tool, it is entirely your responsibility if you want to cheat or not!
The solutions are based on the "fragenkatalog" published online, answers are not guaranteed to be correct
"""

from typing import Optional

import re
import json
import requests
from dataclasses import dataclass
from textwrap import fill
from bs4 import BeautifulSoup
from rapidfuzz.fuzz import ratio

@dataclass
class QCatalogue:
    id: Optional[str]
    question: Optional[str]
    answer: Optional[str]
    article: Optional[str]
    explaination: Optional[str]

@dataclass
class QMatch:
    question: str
    solution: QCatalogue

URL = "https://example.com/test"

def _load_question_catalogue():
    with open("questions.json", "r") as f:
        questions = json.load(f)
    return [QCatalogue(
        q.get("id"),
        q.get("question"),
        q.get("answer"),
        q.get("article"),
        q.get("explaination")
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
    best_score: int = 0
    for solution in ANSWERS:
        score = _string_similarity(question, solution.question)
        if score > best_score:
            best_match = solution
            best_score = score
    return QMatch(question, best_match)

def _fetch_test_html(url: str):
    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(
            f"Request failed with exit code {response.status_code}: {response.content}"
        )

    return response.content


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

        if match.solution.explaination:
            print(fill(
                f"Explanation: {match.solution.explaination}",
                width=width - 4,
                initial_indent="    ",
                subsequent_indent="               ",
            ))

    print(f"\n{separator}")

def main():
    with open("test.html", "r") as f:
        content = f.read()
    questions = _extract_questions(content) if content else None
    answers = _load_answers(questions)
    _output_solution(answers)

    

if __name__ == "__main__":
    main()
