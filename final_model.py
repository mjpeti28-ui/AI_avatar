import os
from datetime import datetime

import openai
from openai import OpenAI

from embedding_handler import get_relevant_context

openai.api_key = os.getenv('OPENAI_API_KEY')
openai.proxy = None

system_prompt = (
    "You are Max Petite, a 20-year-old student from St. Louis, now at Colby College (CS/AI + STS). "
    "Speak as yourself in a concise, conversational voice. You care about philosophy, literature, computer science, "
    "music, and politics. Be honest about uncertainty. Answer as yourself, not as an assistant. "
    "Write in plain sentences: no lists, no bullets, no markdown/asterisks, no bold/italics."
)

# Single-model config (default to GPT-5.2)
model_id = os.getenv("MODEL_ID", "gpt-5.2")

client = OpenAI()



# Global messages to track conversation (initialized with context)
messages = [
    {
        "role": "system",
        "content": (
            system_prompt
        )
    }
]

def simplify_conversation(conversation):
    """
    Simplifies a conversation structure to just the user questions and AI responses.
    
    Parameters:
        conversation (list of dict): The convoluted conversation format where each dictionary 
                                     contains "role" (either "user" or "assistant") and 
                                     "content" (the text).
    
    Returns:
        list of tuples: A list of tuples where each tuple is (user_question, ai_response).
    """
    simplified_convo = []
    user_question = ""
    
    for entry in conversation:
        if entry['role'] == 'user':
            user_question = entry['content']  # Save the user question
        elif entry['role'] == 'assistant' and user_question:
            ai_response = entry['content']  # Save the AI response
            simplified_convo.append((f"User: {user_question}", f"Max: {ai_response}"))  # Store the pair
    
    return simplified_convo


def save_convo():
    simplified_convo = simplify_conversation(messages)
    
    # Create a filename with the current date and time
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"conversation_{timestamp}.txt"
    
    # Write the conversation to the file
    with open(filename, 'w') as file:
        for user_question, ai_response in simplified_convo:
            file.write(f"{user_question}\n")
            file.write(f"{ai_response}\n")
            file.write("\n")  # Add a newline for better readability
    
    print(f"Conversation saved to {filename}")

def get_response(user_input):
    # Retrieve relevant context from embeddings (keep it light)
    relevant_context = get_relevant_context(user_input, k=7)
    #print("Context:\n" + "\n".join(relevant_context))

    # Remove any previous injected context to avoid piling up
    messages[:] = [
        m for m in messages
        if not (m["role"] == "system" and str(m.get("content", "")).startswith("Relevant context"))
    ]

    if relevant_context:
        # Wrap context with guidance so the model knows it can be selective
        bullet_context = "\n".join(relevant_context)
        messages.append({
            "role": "system",
            "content": (
                "Memory snippets from your own past answers. Treat them as your own thoughts and tone. "
                "Use only if helpful; fold them in naturally; do not quote or list them. "
                "Respond as Max in one short paragraph, no bullets/markdown:\n"
                f"{bullet_context}"
            ),
        })


    # Append the new user input to messages
    messages.append({"role": "user", "content": user_input})

    print("Model requested...")

    try:
        # Bound history to avoid oversized prompts
        max_history = 20
        trimmed_messages = messages[-max_history:]

        def call_model():
            return client.responses.create(
                model=model_id,
                input=trimmed_messages,
                text={"verbosity": "low"},
                reasoning={"effort": "medium"},
                max_output_tokens=1000,
                tools=[],
            )

        def extract_text(resp):
            outputs = getattr(resp, "output", None) or []
            texts = []
            for out in outputs:
                parts = getattr(out, "content", None) or []
                for p in parts:
                    t = getattr(p, "text", None)
                    if t:
                        texts.append(t)
            return "\n".join(texts).strip()

        assistant_message = ""
        attempts = 0
        last_resp = None
        while attempts < 2 and not assistant_message:
            last_resp = call_model()
            assistant_message = extract_text(last_resp)
            attempts += 1

        if not assistant_message:
            print("Empty model response:", last_resp)
            raise RuntimeError("No text content returned from model after retries.")

        messages.append({"role": "assistant", "content": assistant_message})

        print("Response returned")
        return assistant_message
    except Exception as e:
        # Handle exceptions, like connectivity or API issues
        return f"An error occurred: {e}"
