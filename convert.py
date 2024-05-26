# A Command Line utility for taking html books like https://artint.info/3e/html/ArtInt3e.html and converting them to pdfs
# This is a quick and dirty tool; no guarantees about quality are made, so use at your own discretion
import base64
import json
import sys
import time
from pypdf import PdfWriter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os
import google.generativeai as genai
import PIL.Image

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY is None:
    print("You must set the GEMINI_API_KEY environment variable to use this tool.")
    exit()
genai.configure(api_key=GEMINI_API_KEY)
# NOTE: This system could possibly be improved by creating a seperate gemini instance dedicated to determining the
# text and the order of the text for the model, that way this system gets to focus on the elements
TABLE_OF_CONTENTS_SYSTEM_PROMPT = """
Generate a table of contents for the book by identifying the sections and subsections in the HTML and screenshot.

The table of contents should just be a simple ordered list of the sections (and subsections in the book).

Return ONLY the table of contents

## User Input (Sample)

### HTML

<!DOCTYPE html>
<html>
<body>

<ol>
    <li><a href="chapter1">Chapter 1</a>
        <ul>
            <li><a href="chapter1/section1">Section 1</a></li>
            <li><a href="chapter1/section2">Section 2</a></li>
            <li><a href="chapter1/section3">Section 3</a></li>
        </ul>
    </li>
    <li><a href="chapter2">Chapter 2</a>
        <ul>
            <li><a href="chapter2/section1">Section 1</a></li>
            <li><a href="chapter2/section2">Section 2</a></li>
            <li><a href="chapter2/section3">Section 3</a></li>
        </ul>
    </li>
    <li><a href="chapter3">Chapter 3</a>
        <ul>
            <li><a href="chapter3/section1">Section 1</a></li>
            <li><a href="chapter3/section2">Section 2</a></li>
            <li><a href="chapter3/section3">Section 3</a></li>
        </ul>
    </li>
    <li><a href="chapter4">Chapter 4</a>
        <ul>
            <li><a href="chapter4/section1">Section 1</a></li>
            <li><a href="chapter4/section2">Section 2</a></li>
            <li><a href="chapter4/section3">Section 3</a></li>
        </ul>
    </li>
    <li><a href="chapter5">Chapter 5</a>
        <ul>
            <li><a href="chapter5/section1">Section 1</a></li>
            <li><a href="chapter5/section2">Section 2</a></li>
            <li><a href="chapter5/section3">Section 3</a></li>
        </ul>
    </li>
</ol>

</body>
</html>

### Screenshot 

(Imagine a screenshot showing the table of contents)

### System Response

1. Chapter 1
    1.1. Section 1
    1.2. Section 2
    1.3. Section 3
2. Chapter 2
    2.1. Section 1
    2.2. Section 2
    2.3. Section 3
3. Chapter 3
    3.1. Section 1
    3.2. Section 2
    3.3. Section 3
4. Chapter 4
    4.1. Section 1
    4.2. Section 2
    4.3. Section 3
5. Chapter 5
    5.1 Section 1
    5.2 Section 2
    5.3 Section 3
"""
SYSTEM_PROMPT = """
This system helps convert HTML books to PDF by identifying elements that link to the next page.

You will be provided with:

* A table of contents of the book
* A list of the urls for previously visited pages (empty on the first page).
* A list of features of the previous page elements that led to the current page (empty on the first page).
* Screenshots and corresponding HTML of the current page of the book.

Note that the first prompt in the series will include the home page (likely the table of contents). Make sure to use this to verify that you visit all of the sections of the book!

Your task is to analyze the HTML and screenshot to identify the element that leads to the next page in the book.

## Expected Output

Return a JSON object with features of the element to click, for example:

{
  "tag": "a",  // Anchor tag
  "href": "chapter2",  // Link on the tag to the next page
  "text": "Next Chapter",  // Minimum text of the tag necessary for matching
  "class": "next-page",  // Classes of the tag
  "id": "NONE"  // Placeholder (if not provided in HTML)
  "log": "'a' tag found in the HTML as well as at the top left of the screen. Text is Next, class is next-page, and it seems tro take you to the next chapter with href='chapter2'" // A log explaining your reasoning for the features
}

## Important Rules

* Avoid revisiting pages; we're trying to create a book, so proper page order is CRUCIAL.
* Return "NONE" if the extracted link (e.g., href attribute) is ALREADY PRESENT in the visited pages list. You can compare the href for the tag to the urls in the previously visited list to avoid revisiting pages.
* DO NOT return 'NONE' unless you have viewed ALL POSSIBLE SECTIONS IN THE TABLE OF CONTENTS and ALL POSSIBLE PAGES WITHIN THEM.
    * Note that the table of contents may not be exhaustive (for example it may not contain subsections), but it should be the MINIMUM number of pages you view 
* Extract features ("tag", "href", "text", "class", "id") directly from the provided HTML.
* When selecting text, most books use tags such as "a" or "link", so you should generally prioritize these
* Include EXACTLY the "text" that you see in the HTML + screenshot to ensure accurate matching. This means including characters like SPACES and PARENTHESIS.
* Do NOT include any escape characters such as "\n" or "\t" in the text.
* Do not combine classes of multiple elements or include uncertain information.
* Verify the consistency of ALL FEATURES using the provided HTML.

## Goal

Provide general features to consistently identify next page elements throughout the book so the book can be converted in the correct order.

## Completion

Once the entire HTML has been processed, return "NONE" for all features to indicate the end of the book conversion.

## User Input (Sample)

### TABLE OF CONTENTS

1. Chapter One
2. Chapter Two
3. Chapter Three
4. Chapter Four
5. Chapter Five

### VISITED PAGES

[]

### PREVIOUS FEATURES

[]

### CURRENT HTML

<!DOCTYPE html>
<html>
<body>

<h1>Chapter 1: Introduction</h1>
<p>This is the first chapter of the book.</p>
<a href="chapter2" class="next-page">Next Chapter</a>

</body>
</html>

### Screenshot 

(Imagine a screenshot showing the text "Chapter 1: Introduction" and clickable text labeled "Next Chapter")

### System Response

{
  "tag": "a",
  "href": "chapter2",
  "text": "Next",
  "class": "next-page",
  "id": "NONE",
  "log": "'a' tag found in the HTML as well as at the top left of the screen. Text is Next, class is next-page, and it seems tro take you to the next chapter with href='chapter2'"
}

### SYSTEM RESPONSE (example on book complete)

{
  "tag": "NONE",
  "href": "NONE",
  "text": "NONE",
  "class": "NONE",
  "id": "NONE",
  "log": "Every single section in the table of contents has been visited in the order specified. Additionally, subsections within the table of contents have been explored as well."
}

## Logging and Debugging

It's helpful to add your reasoning for the features extracted from the HTML or for returning "NONE". This will help improve the program and help you validate the decisions that you make.
"""

table_of_contents_ai = genai.GenerativeModel(
    "gemini-1.5-pro-latest", system_instruction=TABLE_OF_CONTENTS_SYSTEM_PROMPT
)
gemini = genai.GenerativeModel(
    "gemini-1.5-pro-latest", system_instruction=SYSTEM_PROMPT
)

if len(sys.argv) != 4:
    print(
        "Usage: python convert.py <url of table of contents/home page of html book> <output_dir> <title of book>"
    )

# Note that the URL should be the main page containing the table of contents
URL = sys.argv[1]
OUTPUT_DIR = sys.argv[2]
TITLE = sys.argv[3]


def quit(driver, home, merger):
    print("Quitting")
    driver.quit()
    home.close()
    merger.close()
    exit()


def set_content(
    driver,
    width=None,
    height=None,
    max_width=10000,
    max_height=10000,
    timeout=2,
    filter=True,
):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//*[contains(@style, 'overflow-y')]")
            )
        )
    except TimeoutException:
        pass
    # Filter content if set
    if filter:
        filter_content(driver)
    # Set the body to scroll
    driver.execute_script(
        "window.document.body.style.overflowY = 'scroll';",
    )
    # Remove any properties that might constrain the height of the body
    driver.execute_script("window.document.body.style.height = 'auto';")
    driver.execute_script("document.body.style.overflow = 'auto';")
    # Find and unravel any scrollable elements
    vertically_scrollable_elements = driver.find_elements(
        By.XPATH, "//*[contains(@style, 'overflow-y')]"
    )
    for element in vertically_scrollable_elements:
        # Skip the body element
        if element.tag_name == "body":
            continue
        driver.execute_script("arguments[0].style.overflow-y = 'visible';", element)
    scrollable_elements = driver.find_elements(
        By.XPATH, "//*[contains(@style, 'overflow')]"
    )
    for element in scrollable_elements:
        # Skip the body element
        if element.tag_name == "body":
            continue
        driver.execute_script("arguments[0].style.overflow = 'visible';", element)
    # Show all content by setting window height to the height of the body
    if width is None:
        width = driver.execute_script("return window.document.body.scrollWidth")
    if height is None:
        height = driver.execute_script("return window.document.body.scrollHeight")
    driver.set_window_size(min(max_width, width), min(max_height, height))


def save_screenshot(driver, output_path):
    # Method for saving a screenshot of the full website
    try:
        driver.find_element(By.TAG_NAME, "body").screenshot(output_path)
        return True
    except Exception as e:
        print(e)
        return False


# Code adapted from https://github.com/kumaF/pyhtml2pdf/blob/master/pyhtml2pdf/converter.py
def save_pdf(driver, output_path, timeout=2):
    # Method for converting the current page to a pdf
    try:
        WebDriverWait(driver, timeout).until(
            staleness_of(driver.find_element(by=By.TAG_NAME, value="html"))
        )
    except TimeoutException:
        calculated_print_options = {
            "landscape": False,
            "displayHeaderFooter": False,
            "printBackground": True,
            "preferCSSPageSize": True,
        }
        # calculated_print_options.update(print_options)
        resource = (
            "/session/%s/chromium/send_command_and_get_result" % driver.session_id
        )
        url = driver.command_executor._url + resource
        body = json.dumps(
            {"cmd": "Page.printToPDF", "params": calculated_print_options}
        )
        response = driver.command_executor._request("POST", url, body)

        if not response:
            raise Exception(response.get("value"))

        with open(output_path, "wb") as file:
            file.write(base64.b64decode(response.get("value")["data"]))
        return


def initialize_driver():
    # Initialize webdriver
    options = ChromeOptions()
    # options.add_argument("--headless")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--disable-gpu")
    options.add_argument("log-level=3")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    options.add_argument("--start-fullscreen")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    # options.service_args = ["--verbose", "--enable-logging --v=1"]
    # options.set_capability("goog:loggingPrefs", {driver: "ALL"})
    driver = webdriver.Chrome(options=options)
    # driver.implicitly_wait(2)
    return driver


def filter_content(driver):
    """
    Filters content to remove elements that are likely unnecessary for retrieving the book's content
    """
    driver.execute_script(
        """
        var style = document.createElement('style');
        style.innerHTML = `
            @page {
                margin: 0 !important;
                padding: 0 !important;
            }
            header, footer {
                display: none !important;
            }
        `;
        document.head.appendChild(style);
        """
    )


def convert(url, output_dir, title):
    """
    Converts pages to pdfs one at a time and then joins them using pypdf
    """
    print(f"Converting {url} to pdf")
    driver = initialize_driver()
    # original_width = driver.get_window_size()["width"]
    # original_height = driver.get_window_size()["height"]
    driver.get(url)
    # Experimental; set_content_height to the maximum possible height to remove scrollbars
    set_content(driver)

    # Initialize filesystem
    pdf = "{}/part_{}.pdf"
    png = "{}/part_{}.png"
    pdfs = []
    urls = []
    features = []
    screenshot = png.format(output_dir, 0)
    save_screenshot(driver, screenshot)
    home = PIL.Image.open(screenshot)
    save_pdf(driver, pdf.format(output_dir, 0))
    pdfs.append(pdf.format(output_dir, 0))

    print(f"Title: {title}")

    table_of_contents = table_of_contents_ai.generate_content(
        ["**CURRENT HTML**\n" + driver.page_source, PIL.Image.open(screenshot)]
    ).text

    table_of_contents_input = input(
        table_of_contents + "\nIs this table of contents correct? y/n: "
    )
    if table_of_contents_input.lower() != "y":
        print("Table of contents was incorrect!")
        quit(driver, home, writer)

    # Retrieve the HTML, one page at a time
    element_features = {}
    page_num = 1
    while True:
        element_features = get_next_page(
            driver,
            driver.page_source,
            PIL.Image.open(screenshot),
            features,
            urls,
            table_of_contents,
        )
        if element_features is None:
            break
        # Convert the page to a pdf
        save_pdf(driver, pdf.format(output_dir, page_num))
        # Save the pdf
        pdfs.append(pdf.format(output_dir, page_num))
        # Save the screenshot
        save_screenshot(driver, png.format(output_dir, page_num))
        screenshot = png.format(output_dir, page_num)
        # Remove previous screenshot that aren't the home page to save storage
        if page_num - 1 > 0:
            os.remove(png.format(output_dir, page_num - 1))
        page_num += 1
        print(f"Saved page {page_num}")
        urls.append(driver.current_url)
        features.append(element_features)
    os.remove(png.format(output_dir, page_num - 1))
    writer = PdfWriter()
    for pdf in pdfs:
        writer.append(pdf)
    writer.write(f"{output_dir}/{title}.pdf")
    # Remove temporary files
    for pdf in pdfs:
        os.remove(pdf)
    os.remove(png.format(output_dir, 0))
    quit(driver, home, writer)


def get_next_page(
    driver, html, previous_page, previous_features, urls, table_of_contents
):
    """
    Navigates to the next content-filled page in the book and returns it's html
    """
    try:
        element_features = json.loads(
            gemini.generate_content(
                [
                    "### TABLE OF CONTENTS\n"
                    + table_of_contents
                    + "### VISITED PAGES\n"
                    + str(urls)
                    + "\n"
                    + "### PREVIOUS FEATURES\n"
                    + str(previous_features)
                    + "\n"
                    + "### CURRENT HTML\n"
                    + html,
                    previous_page,
                ]
            )
            .text.replace("```json\n", "")
            .replace("```", "")
            .strip()
        )
    except Exception as e:
        # Gemini API exception; delay 60 seconds and then try again
        time.sleep(60)
        element_features = json.loads(
            gemini.generate_content(
                [
                    "### TABLE OF CONTENTS\n"
                    + table_of_contents
                    + "### VISITED PAGES\n"
                    + str(urls)
                    + "\n"
                    + "### PREVIOUS FEATURES\n"
                    + str(previous_features)
                    + "\n"
                    + "### CURRENT HTML\n"
                    + html,
                    previous_page,
                ]
            )
            .text.replace("```json\n", "")
            .replace("```", "")
            .strip()
        )
    print(element_features)
    id = element_features["id"]
    tag = element_features["tag"]
    href = element_features["href"]
    text = element_features["text"]
    element_class = element_features["class"]
    if (
        id == "NONE"
        and tag == "NONE"
        and text == "NONE"
        and element_class == "NONE"
        and href == "NONE"
    ):
        return None
    if tag != "NONE":
        xpath = f"//{tag}["
    else:
        xpath = "//*["
    if href != "NONE":
        xpath += f'contains(@href, "{href}") and '
    if id != "NONE":
        xpath += f'contains(@id, "{id}") and '
    if text != "NONE":
        # xpath += f"contains(., '{text}') and "
        # xpath += f"(child::* | .)[contains(text(), '{text}')] and "
        # xpath += f"(. | descendant-or-self::text())[contains(., '{text}')] and "
        xpath += f'(. | descendant-or-self::text())[contains(normalize-space(.), "{text}")] and '
    if element_class != "NONE":
        xpath += f'contains(@class, "{element_class}") and '
    xpath = xpath[:-5] + "]"
    print(xpath)
    try:
        driver.find_element(By.XPATH, xpath).click()
    except NoSuchElementException:
        # Remove the class definition in the hopes of matching without
        # In case gemini hallucinates class incorrectly
        try:
            xpath = xpath.replace(f' and contains(@class, "{element_class}")', "")
            driver.find_element(By.XPATH, xpath).click()
        except NoSuchElementException:
            try:
                # Try pruning numbers from the text input
                # In case invalid text is the issue
                text_no_nums = "".join([i for i in text if not i.isdigit()])
                xpath = xpath.replace(text, text_no_nums)
                driver.find_element(By.XPATH, xpath).click()
            except NoSuchElementException:
                try:
                    # Try pruning the href from the xpath in case the link is invalid
                    xpath = xpath.replace(f'contains(@href, "{href}") and ', "")
                    driver.find_element(By.XPATH, xpath).click()
                except NoSuchElementException:
                    print("Element not found; final book will not be complete")
                    return None
    set_content(driver)
    previous_page.close()
    return element_features


if __name__ == "__main__":
    convert(URL, OUTPUT_DIR, TITLE)
