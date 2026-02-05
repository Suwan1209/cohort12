"""
By default, deepagents uses claude-sonnet-4-5-20250929. 
You can customize the model used by passing any supported model identifier string or LangChain model object.
"""
# pip install deepagents tavily-python

# =====================================
# Create a search tool
# =====================================

from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from dotenv import load_dotenv
load_dotenv()

tavily_client = TavilyClient()

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

# =====================================
# Create a deep agent
# =====================================
# System prompt to steer the agent to be an expert researcher
research_instructions = """You are an expert researcher. Always answer in Korean.Your job is to conduct thorough research and then write a polished report.
You have access to an internet search tool as your primary means of gathering information.
## `internet_search`
Use this to run an internet search for a given query. You can specify the max number of results to return, the topic, and whether raw content should be included.
"""

agent = create_deep_agent(
    tools=[internet_search],
    system_prompt=research_instructions
)


# =====================================
# Run the agent
# =====================================
# result = agent.stream(
#     {"messages": [{"role": "user", "content": "랭그래프가 모얌?"}]},
#     stream_mode="debug"
# )

# # Print the agent's response
# for chunk in result:
#     print(chunk,"\n")

result = agent.invoke({"messages": [{"role": "user", "content": "랭그래프가 모얌?"}]})

# Print the agent's response
print(result["messages"][-1].content)