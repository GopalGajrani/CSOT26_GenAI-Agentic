import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

def run_chatbot():
    """
    A terminal chatbot that holds a coherent multi-turn conversation.

    Your implementation should:
    - Start with a system message that sets the assistant's behaviour.
    - Maintain a `messages` list with alternating user/assistant turns.
    - Append the assistant's reply to `messages` after each call.
    - Resend the full history on every API call.
    - Allow the user to type 'exit' or 'quit' to end the session.

    Stretch:
    - Add a '/reset' command that clears history so you can feel context loss live.
    - Add a '/tokens' command that prints response.usage after the last call.
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    print("Chat started. Type 'exit' to quit.\n")

    while True:
        # TODO: take user input
        user_input = input("You: ").strip()
        
        
        if user_input.lower()=="exit":
            print("Goodbye!")
            break
            
        if not user_input:
            continue

        # TODO: append the user turn to messages
        messages.append({"role": "user", "content": user_input})
        
        try:
            # TODO: call the API with the full messages list
            response = client.chat.completions.create(
                model="openrouter/free",
                messages=messages
            )

            # TODO: extract the assistant's reply
            ans = response.choices[0].message.content
            
            # TODO: print the reply
            print(f"Assistant: {ans}\n")
            
            # TODO: append the assistant turn to messages
            messages.append({"role": "assistant", "content": ans})
            
        except Exception as e:
            print("Assistant: Sorry, unable to fulfill your request now.\n")
            messages.pop()  

        pass

if __name__ == "__main__":
    run_chatbot()
