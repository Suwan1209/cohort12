"""
Graph 구조 확장 기능

- 입력/출력 schema 분리
- 노드 간 private state 전달
- Pydantic model을 state로 쓰는 경우 런타임 검증
- 여러 노드를 연결한 sequence / branch / loop
- Map-Reduce 스타일 처리 (send API)
- Command API로 state 업데이트+제어 흐름 결합
- 병렬 실행 및 재시도 정책
"""

from langchain.messages import AnyMessage
from typing_extensions import TypedDict

# Define the state
class State(TypedDict):
    messages: list[AnyMessage] 
    # messages: Annotated[list[AnyMessage], operator.add]  
    # messages: Annotated[list[AnyMessage], add_messages]  

    extra_field: int

"""
from langgraph.graph import MessagesState #미리 구축된 것 사용 가능
class State(MessagesState):
    extra_field: int
"""

# =========================================================
# Overwrite
# 기존에 누적되던 상태를 무시, "지금 상태를 기준으로 완전히 새로 시작"해야 할 때 사용
# =========================================================
print(f"\n\n======overwrite======")

from langgraph.graph import StateGraph, START, END
from langgraph.types import Overwrite
from typing_extensions import Annotated, TypedDict
import operator

class State(TypedDict):
    messages: Annotated[list, operator.add]

def add_message(state: State):
    return {"messages": ["first message"]}

def replace_messages(state: State):
    # Bypass the reducer and replace the entire messages list
    return {"messages": Overwrite(["Hello world!"])}

builder = StateGraph(State)
builder.add_node("add_message", add_message)
builder.add_node("replace_messages", replace_messages)

builder.add_edge(START, "add_message")
builder.add_edge("add_message", "replace_messages")
builder.add_edge("replace_messages", END)

graph = builder.compile()

for event in graph.stream(
    {"messages": ["initial"]},
    stream_mode="values",
):
    print(event)

"""
# Can use JSON format(위와 동일한 기능)
def replace_messages(state: State):
    return {"messages": {"__overwrite__": ["replacement message"]}}
"""


# =========================================================
# Define input and output schemas
# 입력은 검사만, 내부 실행은 전체 상태, 출력은 걸러서 돌려줄 수 있다.
# =========================================================
print(f"\n\n======define input and output schemas======")

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# Define the schema for the input
class InputState(TypedDict):
    question: str

# Define the schema for the output
class OutputState(TypedDict):
    answer: str

# Define the overall schema, combining both input and output
class OverallState(InputState, OutputState):
    pass

# Define the node that processes the input and generates an answer
def answer_node(state: InputState):
    # Example answer and an extra key
    return {"answer": "bye", "question": state["question"]}

# Build the graph with input and output schemas specified
builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
builder.add_node(answer_node)
builder.add_edge(START, "answer_node")
builder.add_edge("answer_node", END)
graph = builder.compile()

# 출력 스키마에 따라 반환
print(graph.invoke({"question": "hi"}))


# =========================================================
# Pass private state between nodes
# 노드 간 비공개 상태 전달
# =========================================================
print(f"\n\n======pass private state between nodes======")

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# The overall state of the graph (this is the public state shared across nodes)
class OverallState(TypedDict):
    a: str

# Output from node_1 contains private data that is not part of the overall state
class Node1Output(TypedDict):
    private_data: str

# The private data is only shared between node_1 and node_2
def node_1(state: OverallState) -> Node1Output:
    output = {"private_data": "set by node_1"}
    print(f"Entered node `node_1`:\n\tInput: {state}.\n\tReturned: {output}")
    return output

# Node 2 input only requests the private data available after node_1
class Node2Input(TypedDict):
    private_data: str

def node_2(state: Node2Input) -> OverallState:
    output = {"a": "set by node_2"}
    print(f"Entered node `node_2`:\n\tInput: {state}.\n\tReturned: {output}")
    return output

# Node 3 only has access to the overall state (no access to private data from node_1)
def node_3(state: OverallState) -> OverallState:
    output = {"a": "set by node_3"}
    print(f"Entered node `node_3`:\n\tInput: {state}.\n\tReturned: {output}")
    return output

"""
# add_sequence 
1. 노드 등록 자동
2. 순서대로 엣지 자동 연결
3. 노드 이름도 함수명으로 자동 설정
"""
builder = StateGraph(OverallState).add_sequence([node_1, node_2, node_3])
builder.add_edge(START, "node_1") # 시작은 명시 해야함
graph = builder.compile()

# Invoke the graph with the initial state
response = graph.invoke({"a": "set at start"})

print()
print(f"Output of graph invocation: {response}")


# =========================================================
# Add runtime configuration
# runtime.context = 실행 시점에만 주입되는 설정값 (state에 저장되지 않음)
# runtime.context는 checkpoint / replay 시에도 재실행 시점에만 주입됨
# =========================================================
print(f"\n\n======add runtime configuration======")

from langgraph.graph import END, StateGraph, START
from langgraph.runtime import Runtime
from typing_extensions import TypedDict, Annotated
import operator

# 1. Specify config schema
class ContextSchema(TypedDict):
    my_runtime_value: str

# 2. Define a graph that accesses the config in a node
class State(TypedDict):
    my_state_value: Annotated[str, operator.add]

def node(state: State, runtime: Runtime[ContextSchema]):  
    if runtime.context["my_runtime_value"] == "a":  
        return {"my_state_value": "1"}
    elif runtime.context["my_runtime_value"] == "b":  
        return {"my_state_value": "2"}
    else:
        raise ValueError("Unknown values.")

builder = StateGraph(State, context_schema=ContextSchema)  
builder.add_node(node)
builder.add_edge(START, "node")
builder.add_edge("node", END)

graph = builder.compile()

# 3. Pass in configuration at runtime:
print(graph.invoke({"my_state_value": "0000"}, context={"my_runtime_value": "a"}))  
print(graph.invoke({}, context={"my_runtime_value": "b"}))

"""
# 모델명만 바꾸고 싶을때
response_2 = graph.invoke({"messages": [input_message]}, context={"model_provider": "openai"})["messages"][-1]

# 모델명과 시스템 프롬프트 바꾸고 싶을때
response = graph.invoke({"messages": [input_message]}, context={"model_provider": "openai", "system_message": "Respond in Italian."})
"""

# =========================================================
# Add retry policies
# 재시도 정책 추가
# =========================================================
import sqlite3
from typing_extensions import TypedDict
from langchain.chat_models import init_chat_model
from langgraph.graph import END, MessagesState, StateGraph, START
from langgraph.types import RetryPolicy
from langchain_community.utilities import SQLDatabase
from langchain.messages import AIMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()
db = SQLDatabase.from_uri("sqlite:///:memory:")
db.run("""
CREATE TABLE Artist (
    id INTEGER PRIMARY KEY,
    name TEXT
);
""")
db.run("INSERT INTO Artist (name) VALUES ('A'), ('B');")

model = init_chat_model("claude-haiku-4-5-20251001")

def query_database(state: MessagesState):
    query_result = db.run("SELECT * FROM Artist LIMIT 10;")
    return {"messages": [AIMessage(content=query_result)]}

def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

# Define a new graph
builder = StateGraph(MessagesState)
builder.add_node(
    "query_database",
    query_database,
    retry_policy=RetryPolicy(retry_on=sqlite3.OperationalError),
)
builder.add_node("model", call_model, retry_policy=RetryPolicy(max_attempts=5))
builder.add_edge(START, "model")
builder.add_edge("model", "query_database")
builder.add_edge("query_database", END)
graph = builder.compile()

print(graph.invoke({
    "messages": [HumanMessage(content="DB 조회해줘")]}))


# =========================================================
# Add node caching
# 노드 캐싱 추가
# =========================================================
"""
from langgraph.types import CachePolicy

builder.add_node(
    "node_name",
    node_function,
    cache_policy=CachePolicy(ttl=120),
    # 120초 동안 같은 입력이 들어오면 캐시된 값을 반환
)

from langgraph.cache.memory import InMemoryCache

builder.compile(cache=InMemoryCache()) #컴파일할때 적용해야함
"""

# =========================================================
# 분기(branch) 만들어서 병렬로 돌리고, 다시 합치는(fan-out/fan-in) 방법
# =========================================================
"""
1. 병렬 실행시에는 누적 필드가 필요함, 덮어쓰기 충돌 방지
aggregate: Annotated[list, operator.add] 

2. 한 분기가 더 길때는 defer=True 현재 남아있는 pending task가 0이 될 때까지 기다렸다가 실행
builder.add_node(d, defer=True)  

3. 상태값을 보고 다음에 갈 노드를 런타임에 결정하는 분기, 그래프 내부 if문과 같음
return {"aggregate": ["A"], "which": "c"}  
builder.add_conditional_edges("a", conditional_edge)  
"""


# =========================================================
# Map-Reduce and the send API
# =========================================================
"""
def continue_to_jokes(state: OverallState):
    return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]
"""

# =========================================================
# Create and control loops
# =========================================================
"""
## 종료 조건
def route(state: State) -> Literal["b", END]:
    if len(state["aggregate"]) < 7:
        return "b"
    else:
        return END

builder.add_edge(START, "a")
builder.add_conditional_edges("a", route)

## 종료 조건 실패, LLM 이상 행동, 버그 일때 재귀 방지
from langgraph.errors import GraphRecursionError

try:
    graph.invoke({"aggregate": []}, {"recursion_limit": 4})
except GraphRecursionError:
    print("Recursion Error")
"""

# =========================================================
# Command
# 노드 하나에서 “상태 업데이트 + 다음에 갈 노드 결정”을 동시에
# =========================================================
"""
from langgraph.types import Command

def my_node(state: State) -> Command[Literal["my_other_node"]]:
    return Command(
        # state update
        update={"foo": "bar"},
        # control flow
        goto="my_other_node"
    )

# 서브그래프에서 빠져나와서 메인 그래프의 특정 노드로 이동
return Command(
    update={"foo": "bar"},
    goto="other_subgraph",
    graph=Command.PARENT,
)

# tool이 state를 업데이트(어떤 툴 결과를 이후 전체 그래프에서 계속 써야할 때)
@tool
def lookup_user_info(tool_call_id: Annotated[str, InjectedToolCallId], config: RunnableConfig):
    "Use this to look up user information to better assist them with their questions."
    user_info = get_user_info(config.get("configurable", {}).get("user_id"))
    return Command(
        update={
            # update the state keys
            "user_info": user_info,
            # update the message history, tool message를 추가해야함
            "messages": [ToolMessage("Successfully looked up user information", tool_call_id=tool_call_id)]
        }
    )
"""