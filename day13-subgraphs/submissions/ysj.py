"""
# LangGraph 서브그래프 실전 예제 (LLM 미사용 버전 2)
# 주제: 여행사 일정 예약 시스템 (Travel Itinerary System)
#
# [시나리오]
# 고객이 "목적지"와 "예산"을 제시하면 여행사가 예약을 대행해 줍니다.
# 메인 여행사는 전체 일정만 관리하고, 실제 항공권/호텔 예약 계산은 '예약 전담 시스템'이 처리합니다.
#
# [구조]
# 1. Main Graph (여행사): 고객 요청 접수 -> 예약 시스템(서브그래프) 호출 -> 최종 티켓 발권
# 2. Subgraph (예약 시스템): 항공권 가격 조회 -> 호텔 가격 조회 -> 예산 초과 검사 -> 결과 반환
#
# *LLM 없이 파이썬 로직으로 가격을 계산하고 예산을 검증합니다.
"""

from typing import TypedDict, Optional, Literal
from langgraph.graph import StateGraph, START, END

print("### [실전 예제 2] 여행사 예약 시스템 (Travel Itinerary) ###\n")

# ==============================================================================
# 1. 서브그래프 정의: 예약 전담 시스템 (Booking System)
# ==============================================================================
# 항공권과 숙박료를 계산하고, 예산 내에서 가능한지 판단하는 독립적인 모듈입니다.

class BookingState(TypedDict):
    """예약 시스템 내부 상태"""
    # 입력 데이터
    destination: str
    budget: int
    
    # 내부 계산용 데이터 (메인 그래프는 알 필요 없음)
    flight_cost: int
    hotel_cost: int
    total_cost: int
    
    # 출력 데이터
    booking_status: Literal["CONFIRMED", "FAILED"]
    error_msg: Optional[str]
    booking_ref: str # 예약 확정 번호

def book_flight_step(state: BookingState):
    """1단계: 목적지에 따른 항공권 가격 책정"""
    dest = state["destination"]
    cost = 0
    
    # 목적지별 정찰제 가격 (예시)
    if dest == "Paris":
        cost = 800  # $800
    elif dest == "New York":
        cost = 1200 # $1200
    elif dest == "Jeju":
        cost = 100  # $100
    else:
        # 취급하지 않는 여행지
        return {"booking_status": "FAILED", "error_msg": "취항하지 않는 도시입니다."}
        
    print(f"   [예약팀] '{dest}'행 항공권 확보 (가격: ${cost})")
    return {"flight_cost": cost}

def book_hotel_step(state: BookingState):
    """2단계: 호텔 가격 책정 (이미 실패했으면 스킵)"""
    if state.get("booking_status") == "FAILED":
        return {}
        
    # 호텔은 기본적으로 1박 $200으로 가정
    cost = 200
    print(f"   [예약팀] 스탠다드 호텔 확보 (가격: ${cost})")
    return {"hotel_cost": cost}

def validate_budget_step(state: BookingState):
    """3단계: 총 비용 계산 및 예산 검증"""
    if state.get("booking_status") == "FAILED":
        return {}
    
    total = state["flight_cost"] + state["hotel_cost"]
    
    print(f"   [예약팀] 견적 산출: 총 ${total} (예산: ${state['budget']})")
    
    if total <= state["budget"]:
        return {
            "total_cost": total,
            "booking_status": "CONFIRMED",
            "booking_ref": f"BK-{state['destination'][:3].upper()}-777"
        }
    else:
        return {
            "total_cost": total,
            "booking_status": "FAILED",
            "error_msg": f"예산 ${total - state['budget']} 초과"
        }

# 서브그래프 조립
booking_builder = StateGraph(BookingState)
booking_builder.add_node("book_flight", book_flight_step)
booking_builder.add_node("book_hotel", book_hotel_step)
booking_builder.add_node("validate_budget", validate_budget_step)

booking_builder.add_edge(START, "book_flight")
booking_builder.add_edge("book_flight", "book_hotel")
booking_builder.add_edge("book_hotel", "validate_budget")
booking_builder.add_edge("validate_budget", END)

booking_graph = booking_builder.compile()


# ==============================================================================
# 2. 메인 그래프 정의: 여행사 에이전트 (Travel Agency)
# ==============================================================================
# 고객 응대 및 전체 프로세스를 담당합니다.

class TravelState(TypedDict):
    """여행사 메인 상태"""
    request_id: str
    user_name: str
    destination: str
    user_budget: int
    
    # 결과
    trip_status: str # 'PLANNED', 'BOOKED', 'CANCELLED'
    final_itinerary: str

def consult_step(state: TravelState):
    """1단계: 고객 상담 및 요청 확인"""
    print(f"[여행사] {state['user_name']}님, '{state['destination']}' 여행(예산 ${state['user_budget']})을 계획해 드립니다.")
    return {"trip_status": "PLANNED"}

def delegate_booking_step(state: TravelState):
    """2단계: 예약 시스템(서브그래프) 호출"""
    print(f"[여행사] 예약 담당 부서에 견적을 요청합니다...")
    
    # 1. 서브그래프 입력 매핑
    subgraph_input = {
        "destination": state["destination"],
        "budget": state["user_budget"],
        # 내부 변수 초기화
        "flight_cost": 0,
        "hotel_cost": 0,
        "total_cost": 0
    }
    
    # 2. 서브그래프 실행 (항공/호텔/예산체크 로직 수행)
    result = booking_graph.invoke(subgraph_input)
    
    # 3. 결과 처리
    if result.get("booking_status") == "CONFIRMED":
        itinerary = (
            f"예약 성공! 총 비용 ${result['total_cost']}\n"
            f"        (예약번호: {result['booking_ref']})"
        )
        return {"trip_status": "BOOKED", "final_itinerary": itinerary}
    else:
        fail_reason = result.get("error_msg", "알 수 없는 오류")
        return {"trip_status": "CANCELLED", "final_itinerary": f"예약 실패: {fail_reason}"}

def issue_ticket_step(state: TravelState):
    """3단계: 티켓 발권 및 안내"""
    if state["trip_status"] == "BOOKED":
        print(f"[여행사] 즐거운 여행 되세요! -> {state['final_itinerary']}")
    else:
        print(f"[여행사] 죄송합니다. 여행을 진행할 수 없습니다 -> {state['final_itinerary']}")
    return {}

# 메인 그래프 조립
main_builder = StateGraph(TravelState)
main_builder.add_node("consult", consult_step)
main_builder.add_node("delegate_booking", delegate_booking_step)
main_builder.add_node("issue_ticket", issue_ticket_step)

main_builder.add_edge(START, "consult")
main_builder.add_edge("consult", "delegate_booking")
main_builder.add_edge("delegate_booking", "issue_ticket")
main_builder.add_edge("issue_ticket", END)

app = main_builder.compile()


# ==============================================================================
# 3. 실행 및 테스트 시나리오
# ==============================================================================

if __name__ == "__main__":
    # 시나리오 1: 파리 여행 (예산 충분)
    # 파리($800) + 호텔($200) = $1000 <= 예산($2000) -> 성공
    print("\n--- [시나리오 1] 파리 로맨틱 투어 ---")
    req_1 = {
        "request_id": "REQ-001",
        "user_name": "김철수",
        "destination": "Paris",
        "user_budget": 2000
    }
    app.invoke(req_1)
    
    # 시나리오 2: 뉴욕 여행 (예산 부족)
    # 뉴욕($1200) + 호텔($200) = $1400 > 예산($1000) -> 실패
    print("\n--- [시나리오 2] 뉴욕 비즈니스 트립 ---")
    req_2 = {
        "request_id": "REQ-002",
        "user_name": "이영희",
        "destination": "New York",
        "user_budget": 1000
    }
    app.invoke(req_2)
    
    # 시나리오 3: 없는 지역
    print("\n--- [시나리오 3] 달나라 여행 ---")
    req_3 = {
        "request_id": "REQ-003",
        "user_name": "일론",
        "destination": "Mars",
        "user_budget": 99999
    }
    app.invoke(req_3)