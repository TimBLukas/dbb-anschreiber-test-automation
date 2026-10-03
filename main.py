"""
This is a helper to pass the Anschreiber Test from DBB

I do not take responsibility for using this tool, it is entirely your responsibility if you want to cheat or not!
The solutions are based on the "fragenkatalog" published online, answers are not guaranteed to be correct
"""

from playwright.sync_api import sync_playwright


URL = "https://example.com/test"


def _fetch_test_html(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(URL)
        page.wait_for_load_state("networkidle")

        html = page.content()
        return html


def _extract_questions(html: str):
    pass


def _load_answers(questions: list[str]):
    pass


def _output_solution(answers: list[str]):
    pass


def main():
    html_content = _fetch_test_html(
        "https://dbb.triagonal.net/online/course/view.php?id=18"
    )
    print(html_content)


if __name__ == "__main__":
    main()
