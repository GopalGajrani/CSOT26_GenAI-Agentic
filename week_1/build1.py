import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

def call_model(prompt: str) -> str:
    """
    Make a single chat completion call.
    Print the full response object first and understand its structure.
    Then return just the assistant's text.
    """

    


    response = client.chat.completions.create(
        model="openrouter/free",
        # model="gpt-5",
        messages=[
            {"role": "system", "content": "keep the answer on point, no uneccessary stuff"},
            {"role":"user","content":prompt}
        ],
        # messages=list((response.choices[0].message.content))
    )
    
    # print(response)
    print(response.choices) #-------->gives a huge list which has a lot of information in it including role, message,function_call, tool_call,reasoning and many more details
    # response.usage     ------->tell me about the tokens used in input,output,total_tokens 
    ans=response.choices[0].message.content
    return ans
    # TODO: try adding a system prompt with different instructions and guidelines
    # TODO: inspect `response` before you extract anything from it
    # What's in response.choices? What's in response.usage?
    pass

if __name__ == "__main__":
    print(call_model("What is the capital of Australia?"))
    print(call_model("Who won the 2019 cricket world cup "))
    print(call_model("What was the first question asked by me  "))
