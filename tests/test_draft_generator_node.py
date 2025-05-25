import sys
import os
import logging
import json
from typing import Optional # ✅ Optional을 여기서 임포트!
# --- 1. 기본 설정 및 경로 설정 ---
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

# --- 2. 필요한 모듈 임포트 ---
from langgraph.graph import StateGraph, END
from data.data_models import AgentState, WritingRequirements, CoTStrategyPlan # CoTStrategyPlan도 임포트
from data.sampleRequirements import test_data_set_C #

# 프로젝트의 노드 함수들 (동기 함수로 가정)
from ai_app.Result_generation.Generate_strategy_plan_node import generate_strategy_plan_node #
from ai_app.Result_generation.DraftGeneratorNode import draft_generator_node #

# --- 3. 테스트 데이터 준비 함수 ---
def create_initial_state(test_set_key: str = "C") -> AgentState:
    logger.info(f"테스트 세트 '{test_set_key}'에 대한 초기 AgentState를 생성합니다.")
    data_from_sample = test_data_set_C # 현재는 C 세트만 사용 가정
    
    # WritingRequirements 모델 필드명과 일치하는지 확인 후 생성
    # sampleRequirements.py의 키가 WritingRequirements의 필드명과 정확히 일치해야 함
    # 또는 여기서 명시적인 매핑 로직 추가 필요
    try:
        # WritingRequirements 모델의 모든 필드를 가져와서 sample 데이터에 있는지 확인
        requirements_data = {
            field: data_from_sample.get(field) 
            for field in WritingRequirements.model_fields.keys()
        }
        requirements = WritingRequirements(**requirements_data)
    except Exception as e:
        logger.error(f"WritingRequirements 객체 생성 중 오류 발생: {e}")
        logger.error(f"사용된 데이터: {data_from_sample}")
        logger.error(f"WritingRequirements 필드: {list(WritingRequirements.model_fields.keys())}")
        raise
        
    return AgentState(requirements=requirements) #

# --- 4. LangGraph 워크플로우 정의 ---
def get_writing_pipeline() -> StateGraph:
    logger.info("LangGraph 동기 워크플로우를 정의합니다.")
    workflow = StateGraph(AgentState) #
    workflow.add_node("strategist", generate_strategy_plan_node) #
    workflow.add_node("drafter", draft_generator_node) #
    workflow.set_entry_point("strategist")
    workflow.add_edge("strategist", "drafter")
    workflow.add_edge("drafter", END)
    return workflow

# --- 5. 메인 동기 테스트 실행 함수 ---
def run_sync_test(test_set_key: str = "C"):
    logger.info(f"===== 동기 파이프라인 테스트 시작 (테스트 세트: '{test_set_key}') =====")

    initial_state = create_initial_state(test_set_key)
    logger.info("생성된 초기 요구사항:\n%s", initial_state.requirements.model_dump_json(indent=2))

    graph_definition = get_writing_pipeline()
    app = graph_definition.compile()
    
    logger.info("===== 파이프라인 동기 스트림 실행 시작 =====")
    final_run_state_dict: dict = None # 최종 상태를 저장할 변수 (이제 dict가 될 것임)
    
    for step_output in app.stream(initial_state, {"recursion_limit": 5}):
        if not isinstance(step_output, dict) or not step_output:
            logger.error(f"스트림에서 예기치 않은 출력 형태: {type(step_output)}, 값: {step_output}")
            break

        node_name = list(step_output.keys())[0]
        
        # ✅ --- 중요 수정: current_state_dict는 노드가 반환한 (또는 LangGraph가 변환한) dict ---
        current_state_dict: dict = step_output[node_name] 

        logger.info(f"--- [단계] '{node_name}' 노드 실행 완료 ---")
        # logger.debug(f"'{node_name}' 노드 반환 dict: {current_state_dict}") # 필요시 dict 내용 전체 로깅

        if node_name == "strategist":
            # ✅ dict에서 키로 접근하여 CoTStrategyPlan 객체 가져오기
            plan: Optional[CoTStrategyPlan] = current_state_dict.get("generated_strategy_plan") 
            error_msg: Optional[str] = current_state_dict.get("error_message")

            if plan: # plan이 CoTStrategyPlan 객체인 경우
                logger.info("✅ 전략 생성 완료. 핵심 메시지: %s", plan.core_message)
            elif error_msg:
                logger.error("스트래티지스트 노드 오류: %s", error_msg)
                break 
            else:
                logger.warning("스트래티지스트 노드에서 유효한 plan이나 error_message를 찾을 수 없음.")
        
        elif node_name == "drafter":
            # ✅ dict에서 키로 접근하여 초안 문자열 가져오기
            draft: Optional[str] = current_state_dict.get("current_draft_text")
            error_msg: Optional[str] = current_state_dict.get("error_message")

            if draft:
                logger.info("✅ 초안 생성 완료. 초안 길이: %d 자", len(draft))
            elif error_msg:
                logger.error("드래프터 노드 오류: %s", error_msg)
                break
            else:
                logger.warning("드래프터 노드에서 유효한 draft나 error_message를 찾을 수 없음.")

        final_run_state_dict = current_state_dict

    logger.info("===== 파이프라인 실행 종료 =====")

    if final_run_state_dict and final_run_state_dict.get("current_draft_text"):
        logger.info("\n--- 최종 생성된 초안 ---")
        print(final_run_state_dict["current_draft_text"])
        logger.info("--- 초안 끝 ---")
        logger.info("✅ 테스트 성공: 최종 초안이 생성되었습니다.")
    else:
        logger.error("❌ 테스트 실패: 최종 초안이 생성되지 않았거나, 파이프라인 중간에 오류가 발생했습니다.")
        if final_run_state_dict and final_run_state_dict.get("error_message"):
            logger.error("최종 오류 메시지: %s", final_run_state_dict.get("error_message"))

    logger.info(f"===== 동기 파이프라인 테스트 완료 =====")


# --- 6. 스크립트 실행 ---
if __name__ == "__main__":
    run_sync_test("C")