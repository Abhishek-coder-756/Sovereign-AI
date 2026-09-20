from pypdf import PdfReader
from pathlib import Path


def load_pdf(pdf_path) -> list:

    pdf_path = Path(pdf_path)

    reader = PdfReader(pdf_path)

    documents = []

    for page_number, page in enumerate(reader.pages, start=1):

        text = page.extract_text()

        if text and text.strip():

            documents.append({
                "text": text.strip(),
                "metadata": {
                    "source": pdf_path.name,
                    "page": page_number
                }
            })

    return documents


if __name__ == "__main__":

    pdf_path = "sovereign-ai/data/documents/test.pdf"

    documents = load_pdf(pdf_path)

    print(f"Total pages with text: {len(documents)}")

    for document in documents[:2]:

        print("\n==============================")
        print("SOURCE:", document["metadata"]["source"])
        print("PAGE:", document["metadata"]["page"])
        print("==============================")

        print(document["text"][:1000])