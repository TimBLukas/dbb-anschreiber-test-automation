import fitz
import re
import json
from pathlib import Path


PDF_PATH = Path("kampfrichter_fragenkatalog.pdf")
OUTPUT_PATH = Path("questions.json")


def clean_text(text: str) -> str:
    """Normalize whitespace and line breaks."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_questions(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)

    # Combine the text from all PDF pages
    full_text = "\n".join(page.get_text() for page in doc)

    # Find question numbers such as K-1, K-2, ..., K-142
    matches = list(re.finditer(r"(?m)^K-(\d+)\s*", full_text))

    questions = []

    for index, match in enumerate(matches):
        question_number = int(match.group(1))

        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(full_text)
        )

        block = full_text[start:end]

        # Find the answer, e.g. "Ja (Art. 3)." or "Nein (KRHB)."
        answer_match = re.search(
            r"\b(Ja|Nein)\s*(?:\(([^)]*)\))?\.",
            block
        )

        if not answer_match:
            print(f"Warning: no answer found for K-{question_number}")
            continue

        # -------------------------
        # Question
        # -------------------------

        question = block[:answer_match.start()]

        # Remove the x from the J/N column
        question = re.sub(
            r"\bx\b",
            "",
            question,
            flags=re.IGNORECASE
        )

        question = clean_text(question)

        # -------------------------
        # Answer
        # -------------------------

        answer = answer_match.group(1)

        # Reference inside the parentheses
        answer_reference = answer_match.group(2)

        # -------------------------
        # Explanation
        # -------------------------

        explanation = block[answer_match.end():]

        # Remove PDF footer
        explanation = re.sub(
            r"\s*1\.8\.2026\s+\d+\s+von\s+17\s*$",
            "",
            explanation
        )

        explanation = clean_text(explanation)

        # -------------------------
        # Article
        # -------------------------

        article = None

        lines = [
            line.strip()
            for line in explanation.split("\n")
            if line.strip()
        ]

        if lines:
            last_line = lines[-1]

            # Examples:
            # 3
            # 29/51
            # 43
            if re.fullmatch(r"\d+(?:/\d+)*", last_line):
                article = last_line
                explanation = clean_text(
                    "\n".join(lines[:-1])
                )

            # Example:
            # KRHB
            elif re.fullmatch(
                r"[A-Za-zÄÖÜäöüß-]+",
                last_line
            ):
                article = last_line
                explanation = clean_text(
                    "\n".join(lines[:-1])
                )

        question_data = {
            "id": f"K-{question_number}",
            "question": question,
            "answer": answer,
            "article": article,
            "explanation": explanation,
        }

        questions.append(question_data)

    return questions


def main():
    questions = parse_questions(PDF_PATH)

    # Sort questions by their number
    questions.sort(
        key=lambda q: int(q["id"].split("-")[1])
    )

    # Write JSON output
    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            questions,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print(f"{len(questions)} questions extracted.")
    print(f"Output: {OUTPUT_PATH}")

    # Validate question numbers
    expected = list(range(1, len(questions) + 1))

    actual = [
        int(q["id"].split("-")[1])
        for q in questions
    ]

    if actual == expected:
        print("Question numbers are complete and sequential.")
    else:
        print("Warning: missing or duplicate question numbers.")

    # Check for missing fields
    missing = []

    for question in questions:
        if not question["question"]:
            missing.append((question["id"], "question"))

        if not question["answer"]:
            missing.append((question["id"], "answer"))

    if missing:
        print("Missing fields:")

        for item in missing:
            print("  ", item)
    else:
        print("All questions contain a question and an answer.")


if __name__ == "__main__":
    main()