I really enjoyed working on week 1 repo. I felt quite nervous before starting the work that I would not be able to do it as have never worked in Gen AI field and never used api keys and all.

I found the resources really useful, initially I was not comfortable with the syntax and all but I kept trying hard and finally things became clear, I loved reading resources about the stuff I have to perform .
open AI develoopers website was quite engaging , I kept reading the resources for fun tried to find the different ways to get a response , what are inbuilt functions to compact and conversation guide on the website was quite useful.

Initially I tried using different AI models but things didn't work it showed me error about token_limit exceed so then I switched to 
"openrouter/free" model.

I understood the importance the role of system which ultimately decides how would our chat agent respond , it also helped me sumamrise the conversations.

I did many mistakes during this entire week but those mistakes were worth commiting as they gave me better clarity towards GEN AI 

Few mistakes which I did include - 
    1. I used wrong input format 
    2. Even though I compacted the conversation but when max_limit is hit then in the free model it eventually end up at initial conversation being dropped.
    3.In delete_memory we can't simply clear the history we need to leave it 1st element as it is as system decides how our chatagent will behave
    4.I saved the summary to the content of system , the very first element of history.Since I cannot delete the element having content for role of system hence it ended up saving the memory.So when i called the delete_memory function and then asked it a question related to previous topics then it gave me the correct result . Hence I cant simply add the content to 1st element and hence I corrected it later .



At the end of week 1 I gained confidence and really loved working on this multiturn Chatbot. I loved the way I explored different resources and implemented it .