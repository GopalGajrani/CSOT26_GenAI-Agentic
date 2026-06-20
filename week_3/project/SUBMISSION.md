Navigate to week_3/project/ and run pip install -r requirements.txt to install the external packages(required for this weeks task)

This week had a lot to learn , building a research bot initially i felt what is difference between week_2 and week_3 taask , they were quite similar 
But this week had thougt me to have a look on every minute thing which could give wring results , i spend hours just find a minute bug and later realised that it was the one of a kind i have ignored so far, i learnt how to work with directories in a much deeper way and how to exactly direct the files and path to any files,Earlier i was not much comfortable with directories and all. 
Even oops logic was good and great to learn , and also i became mroe comfortable with json .

It was difficult for me to understand the content given in _paper_tools.md i didn't knew how do i search it , what's the syntax and the hugging face website was so uncomfortable , it had a very small icon on the left bar with had api docs and the syntax there was so bad, so explored requests library and done through it ,

One strange thing which i observed was when i ran my build_2 without importing any other tools then files.py it had a instruction from AGENT.md so sometimes it shown me [TOOL] : web_search which was strange because it had no tool named web_search 

And also my files were getting saved to wrong folder since i copy pasted the workspace root from build_2 directly into the agents and tools files , but they both were in the different folder and hence had to change that ,
Honestly i am still not comfortable with textual , and also don't know why are my key bindings not working when i am using ctrl+q and ctrl+k, for the same function if i am usin any other key combination then it is working .
Importing tools and functions from one file to another was new to me , i didn't worked with earlier so enjoyed doing that and saved a lot of time instead of copying those tools and pasting it again, code looks more pretty and compact with functions imported .
But this week content i felt was not in detail , at some point i was stucked for hours and kept searching for relevant sources , as a beginner it is not easy to get comfortable with these new things so onlu thing i would say is which i am saying from past 2 weeks a more detailed content would be appreciated and a proper starting guide of how and where to start and TODO points more specified in the code, because while working was this i lagged confidence at many points wether I am doing correct or not . 

This week i had a better clarity of what I am doing and the proper workflow but it took long to gain that understanding . And this week task was much based on smaller components and then integrating them into a Research desk , hence i had to be very focused in making my smaller elements (tools).

Technical Design Decisions-
Line-based File Edits and Diff Previews -> Instead of allowing the LLM to rewrite entire files (which is error-prone and context-heavy), the agent uses line-based editing. The read_file tool returns line numbers prefixed to each line (e.g., 1 : text). The edit_file tool then expects exact line ranges (start_line to end_line) and an operation (insert, replace, delete, append)

Sandbox Enforcement via resolve_path -> To prevent the agent from escaping the project directory and preventing it from accessing sensitive system files (e.g., /etc/passwd), all file tools has to check resolve_path function first. It uses os.path.abspath(os.path.join(WORKSPACE_ROOT, path)) and verifies that the resulting absolute path starts with the WORKSPACE_ROOT. If it doesn't, it immediately raises a ValueError("Path escapes workspace").

Session History Streaming and Persistence-> sessions are saved to .agent/sessions/<id>.json and instead of blindly appending the raw messages to LLM upon reload , it also updates system prompt so that it system prompt remains uptodate.