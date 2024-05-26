# htmlbooktopdf

Converts html books to pdfs by identifying the overall structure of the book and the features of the navigation elements in the book, and using these features to traverse the book and compile a complete pdf.

## Usage

Set the **GEMINI_API_KEY** variable with your **GEMINI_API_KEY**; a .env file in the project directory will work fine!

```
pip install -r requirements.txt
```

```
python convert.py <url of table of contents/home page of html book> <output_dir> <title of book>
```

## Limitations

- This project relies on Google's Gemini LLM; I can't guarantee consistent results for every webpage, but you can fine-tune the model for specific websites and use some of the utilities in convert.py to increase your likelihood of success
- This project also relies on Selenium WebDriver; this, in combination with Gemini, causes the conversion
- Has only been tested on TWO HTML BOOKS (see test.py and test_output/ for more details) and the results for these haven't been totally verified; I think it could use a couple more, so feel free to use it and PR your test_output along with any suggestions to improve the functionality!
