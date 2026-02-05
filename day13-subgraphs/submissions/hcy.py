import random
from typing import TypedDict, Literal
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

load_dotenv()
model = ChatOpenAI(model="gpt-4o", temperature=0.7)

print("⚡ 빠르모트 키우기 v2.0 (UX 개선판) ⚡\n")

# ======================================================
# 0. 공통 상태
# ======================================================
class PokemonState(TypedDict):
    name: str
    level: int
    hp: int
    max_hp: int
    pp: int
    max_pp: int
    attack: int
    speed: int
    log: str
    next_action: str

# ======================================================
# 1. 🏋️ 서브그래프: 훈련 (Training)
# ======================================================
def train_node(state: PokemonState):
    atk_gain = random.randint(1, 3)
    spd_gain = random.randint(1, 3)
    hp_cost = 10

    new_hp = max(0, state['hp'] - hp_cost)
    new_atk = state['attack'] + atk_gain
    new_spd = state['speed'] + spd_gain

    # [수정] 3문장 이내로 짧게 제한
    prompt = f"""
    당신은 포켓몬 트레이너입니다. '{state['name']}'가 훈련하는 모습을 묘사해주세요.
    
    [제약사항]
    1. **최대 3문장**으로 간결하게 작성하세요.
    2. 너무 장황한 미사여구는 빼주세요.
    3. 마지막엔 "공격력이 {atk_gain}, 스피드가 {spd_gain} 상승했다!"라고 덧붙이세요.
    """
    msg = model.invoke(prompt)

    return {
        "hp": new_hp,
        "attack": new_atk,
        "speed": new_spd,
        "log": msg.content
    }

train_builder = StateGraph(PokemonState)
train_builder.add_node("train_logic", train_node)
train_builder.add_edge(START, "train_logic")
train_subgraph = train_builder.compile()


# ======================================================
# 2. ⚔️ 서브그래프: 배틀 (Battle)
# ======================================================
def battle_node(state: PokemonState):
    if state['hp'] <= 10 or state['pp'] <= 0:
        return {"log": "⚠️ 체력이나 PP가 부족해서 싸울 수 없어! (아이템을 사용해)"}

    enemy = random.choice(["꼬렛", "피카츄", "망나뇽", "이브이"])
    damage = random.randint(10, 25)
    pp_cost = 5

    new_hp = max(0, state['hp'] - damage)
    new_pp = max(0, state['pp'] - pp_cost)

    # [수정] 줄바꿈 요청 및 요약 추가
    prompt = f"""
    야생의 '{enemy}'(이)가 나타났다! '{state['name']}'와의 전투를 묘사해줘.
    
    [제약사항]
    1. **3문장 이내**로 짧고 박진감 넘치게 쓰세요.
    2. 기술 이름('전광석화', '인파이트')이 나올 때는 **반드시 앞에 줄바꿈(\n)**을 넣어주세요.
    3. 결과적으로 {damage}의 피해를 입었다는 내용을 포함하세요.
    """
    msg = model.invoke(prompt)

    # [수정] 전투 결과 강제 요약 (LLM에게 맡기지 않고 직접 붙임)
    summary_stat = f"\n\n📊 [전투 결과]\n- HP: {state['hp']} -> {new_hp} (-{damage})\n- PP: {state['pp']} -> {new_pp} (-{pp_cost})"

    return {
        "hp": new_hp,
        "pp": new_pp,
        "log": msg.content + summary_stat
    }

battle_builder = StateGraph(PokemonState)
battle_builder.add_node("battle_logic", battle_node)
battle_builder.add_edge(START, "battle_logic")
battle_subgraph = battle_builder.compile()


# ======================================================
# 3. 💊 서브그래프: 아이템 (Item)
# ======================================================
def item_node(state: PokemonState):
    # [수정] 서브그래프 안에서 유저에게 직접 물어봄 (Interrupt)
    choice = interrupt("사용할 아이템을 선택하세요:\n1. 상처약 (HP 회복)\n2. PP에이드 (PP 회복)\n3. 이상한사탕 (Level Up)\n👉 선택: ")

    log_msg = ""
    updates = {}

    if choice == "1":
        updates = {"hp": state['max_hp']}
        log_msg = "💊 [상처약]을 사용했습니다. 체력이 모두 회복되었습니다!"

    elif choice == "2":
        updates = {"pp": state['max_pp']}
        log_msg = "🧪 [PP에이드]를 사용했습니다. 기술 횟수가 충전되었습니다!"

    elif choice == "3":
        updates = {
            "level": state['level'] + 1,
            "max_hp": state['max_hp'] + 5,
            "hp": state['max_hp'] + 5 # 체력도 회복
        }
        log_msg = f"🍬 [이상한사탕] 꿀꺽! 레벨이 올랐습니다! (Lv.{state['level'] + 1})"

    else:
        log_msg = "❌ 아이템 사용을 취소했습니다."

    return {**updates, "log": log_msg}

item_builder = StateGraph(PokemonState)
item_builder.add_node("item_logic", item_node)
item_builder.add_edge(START, "item_logic")
item_subgraph = item_builder.compile()


# ======================================================
# 4. 🕹️ 메인 그래프: 매니저
# ======================================================
def manager_node(state: PokemonState):
    # [수정] 메인 화면에서는 로그를 아주 짧게 요약해서 보여줌
    short_log = state.get('log', '')
    if len(short_log) > 40:
        short_log = short_log[:40] + "..."

    status_screen = f"""
    ========================================
    ⚡ {state['name']} (Lv.{state['level']}) ⚡
    ----------------------------------------
    ❤️ HP: {state['hp']} / {state['max_hp']}
    💧 PP: {state['pp']} / {state['max_pp']}
    ⚔️ ATK: {state['attack']} | 💨 SPD: {state['speed']}
    ========================================
    [최근 상황]: {short_log}
    """
    print(status_screen)

    # 2. 사용자 입력
    user_choice = interrupt("\n행동 선택 (1:훈련 / 2:배틀 / 3:아이템 / q:종료): ")
    return {"next_action": user_choice}

def route_action(state: PokemonState):
    choice = state.get("next_action")
    if choice == "1": return "go_train"
    elif choice == "2": return "go_battle"
    elif choice == "3": return "go_item"
    else: return "go_end"

builder = StateGraph(PokemonState)
builder.add_node("manager", manager_node)
builder.add_node("TrainingGym", train_subgraph)
builder.add_node("BattleArena", battle_subgraph)
builder.add_node("ItemShop", item_subgraph)

builder.add_edge(START, "manager")
builder.add_conditional_edges("manager", route_action,
                              {"go_train": "TrainingGym", "go_battle": "BattleArena", "go_item": "ItemShop", "go_end": END})
builder.add_edge("TrainingGym", "manager")
builder.add_edge("BattleArena", "manager")
builder.add_edge("ItemShop", "manager")

checkpointer = InMemorySaver()
game_app = builder.compile(checkpointer=checkpointer)


# ======================================================
# 5. 실행 루프
# ======================================================
initial_state = {
    "name": "빠르모트", "level": 50,
    "hp": 100, "max_hp": 100,
    "pp": 20, "max_pp": 20,
    "attack": 120, "speed": 105,
    "log": "모험을 떠날 준비가 되었습니다.",
    "next_action": ""
}

config = {"configurable": {"thread_id": "save_v2"}}
print("--- 🎮 Game Start 🎮 ---")
game_app.invoke(initial_state, config)

while True:
    snapshot = game_app.get_state(config)
    if not snapshot.next:
        print("\n게임을 종료합니다. 펭-바! 🐧")
        break

    if snapshot.tasks and snapshot.tasks[0].interrupts:
        interrupt_obj = snapshot.tasks[0].interrupts[0]

        # 질문 내용 출력 (매니저 질문 or 아이템 상점 질문)
        print(f"👉 {interrupt_obj.value}")

        user_input = input("입력: ")
        if user_input.lower() == 'q':
            print("저장하지 않고 종료합니다.")
            break

        # 행동 결과를 바로 보여주기 위해 여기서 결과 확인 (UX 개선)
        # resume을 실행하면 그래프가 다음 단계로 넘어감
        result = game_app.invoke(Command(resume=user_input), config)

        # [수정] 행동 직후에는 전체 로그를 시원하게 보여줌!
        if "log" in result:
            print(f"\n📝 [Action Log]\n{result['log']}")
            print("-" * 30)