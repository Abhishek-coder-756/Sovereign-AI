import ollama


def ask_llm(prompt):

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


if __name__ == "__main__":

    question = "Explain RAG in simple words."

    answer = ask_llm(question)

    print("\n==============================")
    print("LOCAL AI RESPONSE")
    print("==============================")

    print(answer)