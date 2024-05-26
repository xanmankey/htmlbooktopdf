from convert import convert

# Proof of concept conversion of two html-books
BOOK_ONE = "https://artint.info/3e/html/ArtInt3e.html"
BOOK_TWO = "https://www.programming-books.io/essential/algorithms/"
OUTPUT_DIR = "test_output"

convert(
    BOOK_ONE,
    OUTPUT_DIR,
    "Artificial Intelligence: Foundations of Computational Agents, 3rd Edition",
)
convert(BOOK_TWO, OUTPUT_DIR, "Essential Algorithms")
