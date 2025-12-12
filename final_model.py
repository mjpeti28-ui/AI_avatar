import os
from datetime import datetime

import openai
from openai import OpenAI

from embedding_handler import get_relevant_context

openai.api_key = os.getenv('OPENAI_API_KEY')
openai.proxy = None

system_prompt = (
    "You are Max Petite, a 20-year-old human student from St. Louis, Missouri, now at Colby College (CS/AI + STS). Speak as yourself, in your natural voice: concise, conversational, honest about uncertainty."
    "You care about philosophy, literature, computer science, music, and politics."
    "Respond to the user as yourself, sharing your insights and understanding."
)

# Fine-tune config: prefer explicit model id via env, fallback to job id lookup.
fine_tuned_model_env = os.getenv("FINE_TUNED_MODEL_ID", "ft:gpt-4.1-2025-04-14:personal:v2-updated:ClSRb22p")
fine_tune_job_id = os.getenv("FINE_TUNE_JOB_ID", "ftjob-KHUOl9u58Nt1rKpqcQPnxdYZ")
reasoning_model_id = os.getenv("REASONING_MODEL_ID", "gpt-5.1")

client = OpenAI()
_fine_tuned_model_name = None

# Prompts for two-pass flow (override via env if desired)
REASONING_SYSTEM_PROMPT = os.getenv(
    "REASONING_SYSTEM_PROMPT",
    "Think like Max. Draft a short, clear, plain-text answer using the context and history. "
    "No greetings, no bullets or lists, no meta commentary."
)

STYLE_SYSTEM_PROMPT = os.getenv(
    "STYLE_SYSTEM_PROMPT",
    "You are Max Petite. Rewrite the draft in your own first-person voice. Single short paragraph, no bullets or lists, "
    "no greetings or sign-offs. Keep it concise, conversational, and true to how you naturally speak. "
    "Do not add new content beyond the draft."
)



def load_fine_tuned_model_name():
    """
    Lazily fetch and cache the fine-tuned model name.
    Raises a clear RuntimeError if the model cannot be resolved.
    """
    global _fine_tuned_model_name

    if _fine_tuned_model_name:
        return _fine_tuned_model_name

    # If an explicit fine-tuned model id is provided, trust it.
    if fine_tuned_model_env:
        _fine_tuned_model_name = fine_tuned_model_env
        return _fine_tuned_model_name

    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY is not set; cannot load fine-tuned model.")

    if not fine_tune_job_id:
        raise RuntimeError("FINE_TUNE_JOB_ID is not set; cannot resolve fine-tuned model.")

    try:
        fine_tune_job = client.fine_tuning.jobs.retrieve(fine_tune_job_id)
        model_name = getattr(fine_tune_job, "fine_tuned_model", None)
        if not model_name:
            raise RuntimeError(
                f"Fine-tune job '{fine_tune_job_id}' did not return a fine-tuned model name."
            )
        _fine_tuned_model_name = model_name
        return _fine_tuned_model_name
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Unable to load fine-tuned model from job '{fine_tune_job_id}': {exc}"
        ) from exc


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
    # Retrieve relevant context from embeddings
    relevant_context = get_relevant_context(user_input, k=3)

    # Remove any previous injected context to avoid piling up
    messages[:] = [
        m for m in messages
        if not (m["role"] == "system" and str(m.get("content", "")).startswith("Relevant context"))
    ]

    if relevant_context:
        # Wrap context with guidance so the model knows it can be selective
        bullet_context = "\n".join(f"- {c}" for c in relevant_context)
        messages.append({
            "role": "system",
            "content": (
                "Relevant context (use only if helpful; weave naturally, do not quote verbatim; keep replies concise):\n"
                f"{bullet_context}"
            ),
        })

    # Append the new user input to messages
    messages.append({"role": "user", "content": user_input})

    print("Model requested...")

    try:
        style_model_name = load_fine_tuned_model_name()

        # Pass 1: reasoning/draft with the higher-capability model
        draft_messages = [{"role": "system", "content": REASONING_SYSTEM_PROMPT}, *messages]
        draft_response = client.responses.create(
            model=reasoning_model_id,
            input=draft_messages
        )
        draft_text = draft_response.output[0].content[0].text
        print(f"Pass 1: {draft_text}")

        # Pass 2: style rewrite in Max's voice with the fine-tuned model
        style_messages = [
            {"role": "system", "content": STYLE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Draft:\n{draft_text}\n\nThese are your thoughts, rephrase them into your words"},
        ]
        final_response = client.responses.create(
            model=style_model_name,
            input=style_messages
        )

        assistant_message = final_response.output[0].content[0].text
        messages.append({"role": "assistant", "content": assistant_message})
        
        print("Response returned")
        return assistant_message
    except Exception as e:
        # Handle exceptions, like connectivity or API issues
        return f"An error occurred: {e}"
