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
from bs4 import BeautifulSoup
from rapidfuzz.fuzz import ratio


class QCatalogue:
    id: Optional[str]
    question: Optional[str]
    answer: Optional[str]
    article: Optional[str]
    explanation: Optional[str]


URL = "https://example.com/test"

def _load_question_catalogue():
    with open("questions.json", "r") as f:
        questions = json.load(f)
    return questions
ANSWERS = _load_question_catalogue()



def normalize(s: str):
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def _string_similarity(s1: str, s2: str):
    return ratio(normalize(s1), normalize(s2))

def _fetch_test_html(url: str):
    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(
            f"Request failed with exit code {response.status_code}: {response.content}"
        )

    return response.content


def _extract_questions(html: str) -> list[str]:
    """Extract the question text from a Moodle quiz page."""
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

def _load_answer(question: str):
    pass

def _load_answers(questions: list[str]):
    return [_load_answer(q) for q in questions]


def _output_solution(answers: list[str]):
    pass


def main():
    with open("test.html", "r") as f:
        content = f.read()
    questions = _extract_questions(content) if content else None
    for q in questions:
        print(q)

    

if __name__ == "__main__":
    main()
