import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
print("Hi i am Your Ai assistant, please type Exit to end the chat !")
# tokens=0
history=[{"role":"system","content":"Keep the answers on point"}]
while True:
    prompt=input("You :")
    
    if(prompt!="Exit"):
        history.append({"role":"user","content":prompt})

        
# ---------------------------USING RESPONSES METHOD ----------------------------------------
        # response=client.responses.create(
        #     instructions="You are a helpful assistant, please be on point while answering !",
        #     model="openrouter/free",
        #     input=history[-1]["content"])
        #     # store=True
        # history.append({"role":"assitant","content":response.output_text})

        # print(response.output_text)
        

        # print(response ,"\n")
        # print(response.max_output_tokens,"\n")
        # print(response.usage.total_tokens)

        
# ---------------------------USING CHAT COMPLETIONS METHOD -----------------------------------------
        response=client.chat.completions.create(
            model="openrouter/free",
            messages=history
        )





        ans=response.choices[0].message.content
        print()
        history.append({"role":"assistant","content":ans})
        # print(history)
        print(response.choices[0].message.role," : ",ans)

    else:
        print("Thank you , have a nice day !")
        break
