from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_documents(documents):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )

    chunks = []

    for document in documents:

        text_chunks = splitter.split_text(document["text"])

        for chunk in text_chunks:

            chunks.append({
                "text": chunk,
                "metadata": document["metadata"]
            })

    return chunks


if __name__ == "__main__":

    from pdf_loader import load_pdf

    pdf_path = "sovereign-ai/data/documents/test.pdf"

    documents = load_pdf(pdf_path)

    chunks = chunk_documents(documents)

    print("Total documents:", len(documents))
    print("Total chunks:", len(chunks))

    for i, chunk in enumerate(chunks[:3]):

        print("\n==============================")
        print("CHUNK:", i + 1)
        print("SOURCE:", chunk["metadata"]["source"])
        print("PAGE:", chunk["metadata"]["page"])
        print("==============================")

        print(chunk["text"])