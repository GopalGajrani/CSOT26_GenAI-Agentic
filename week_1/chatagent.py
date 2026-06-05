import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()


class ChatAgent:
    def __init__(self, model_name="openrouter/free", max_turns=10):
        # Initialize OpenRouter Client
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        self.model = model_name
        self.max_turns = max_turns
        
        # Checklist: Chatbot holds a coherent conversation (Memory)
        self.history = [{"role": "system", "content": "You are a helpful and concise AI assistant.To save tokens keep answers on point "}]   # it was giving unnnecessary details hence had to define system prompt

    # Checklist: Implement the earlier call_model as a method
    def call_model(self, prompt):
        
        self.history.append({"role": "user", "content": prompt})
        try:
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history
            )

            ans=response.choices[0].message.content
            print("Assistant : ",ans)
            print()       #clean new line to avoid output being messy 
            
        except Exception as e:
            print("Sorry, unable to fulfill you request now.")
            self.history.pop()

            return

        
        self.history.append({"role": "assistant", "content": ans})

        
        self._check_buffer()

    def _check_buffer(self):
 
        current_turns = (len(self.history) - 1) / 2     # -1 for the intital system prompt
        
        if current_turns > self.max_turns:
            print("\n[System: Max tokens reached. Compacting chat history into a summary...]")
            self.compact_history()


    def compact_history(self):

        
        compaction_prompt =("Summarize the core facts of this conversation in exactly one or two short, natural sentences. "
            "Do not use bullet points and repetitions are discouraged . Skip all greetings, fluff, and do not announce that you are summarizing. "
            "Just state the actual information discussed.")
        temp_history = self.history.copy()
        temp_history.append({"role": "user", "content": compaction_prompt})
        
        summary_response = self.client.chat.completions.create(
            model=self.model,
            messages=temp_history
        )
        
        summary_text = summary_response.choices[0].message.content
        
        # Overwrite old history with just the new summary
        self.history = [

# -------------------after it summarises then delete won't function properly---------------
            # {"role": "system", "content": f"You are a helpful assistant. Here is a summary of the conversation so far: {summary_text}"}    

         {"role":"system","content":"You are a helpful assitant"},
         {"role":"system","content":f"Here is the summary so far....\n {summary_text}"}
        ]
        print("The summarised conversation for you : \n",summary_text)
    
    def delete_memory(self): 

        del self.history[1:]      #the system prompt need to be there in history
        print("Assistant : ","All the history cleared")
        

# ==========================================
# Main Execution Loop
# ==========================================
if __name__ == "__main__":
    print("Welcome to the ChatAgent!")
    print("Available Models:")
    print("1. openrouter/free (Default - Free)")
    print("--- OpenAI (ChatGPT) ---")
    print("2. openai/gpt-4o-mini")
    print("3. openai/gpt-4o")
    print("--- Anthropic (Claude) ---")
    print("4. anthropic/claude-3.5-sonnet")
    print("--- Google (Gemini) ---")
    print("5. google/gemini-2.5-flash")
    print("--- DeepSeek ---")
    print("6. deepseek/deepseek-chat (DeepSeek V3)")
    print("7. deepseek/deepseek-r1:free (DeepSeek R1)")

    choice = input("\nSelect a model (1-7) or press Enter for default: ")
    
  
    selected_model = "openrouter/free"
    

    # When i tried using different models , it failed showing me more tokens used than allowed but when i did the same thing with model="openrouter/free" it worked
    if choice == "2":
        # selected_model = "openai/gpt-4o-mini"
        print("Assistant : ", "Sorry this version can't be used at the moment")
    elif choice == "3":
        # selected_model = "openai/gpt-4o"
        print("Assistant : ", "Sorry this version can't be used at the moment")
    elif choice == "4":
        # selected_model = "anthropic/claude-3.5-sonnet"
        print("Assistant : ", "Sorry this version can't be used at the moment")
    elif choice == "5":
        # selected_model = "google/gemini-2.5-flash"
        print("Assistant : ", "Sorry this version can't be used at the moment")
    elif choice == "6":
        # selected_model = "deepseek/deepseek-chat"
        print("Assistant : ", "Sorry this version can't be used at the moment")
    elif choice == "7":
        # selected_model = "deepseek/deepseek-r1:free"
        print("Assistant : ", "Sorry this version can't be used at the moment")

    agent = ChatAgent(model_name=selected_model, max_turns=5)
    
    print(f"\n[{selected_model} loaded. Type 'Exit' to quit, or 'compact' to manually summarize history or 'delete memory' to delete the memory.]")

    # The continuous conversation loop
    while True:
        user_input = input("\nYou: ")
        
 
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        elif user_input.lower() == "compact":     #for manually summarising before hitting max limit
            agent.compact_history()
            # print(agent.history)
        elif user_input.lower()=="delete memory":   #to check how the chatbot behaves if previous context is deleted
            agent.delete_memory()
        else:
            agent.call_model(user_input)