# test_finalizer_node.py
import sys
import os
import logging
import json
from typing import Optional

# --- 1. 경로 설정 및 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

# --- 2. 필요한 모듈 임포트 ---
from langgraph.graph import StateGraph, END
from data.data_models import AgentState, WritingRequirements
from data.sampleRequirements import test_data_set_A

from ai_app.Result_generation.Generate_strategy_plan_node import generate_strategy_plan_node
from ai_app.Result_generation.DraftGeneratorNode import draft_generator_node
from ai_app.Result_generation.MetadataGeneratorNode import metadata_generator_node
from ai_app.Result_generation.FinalizerNode import finalizer_node

# --- 3. 초기 상태 생성 함수 ---
def create_initial_state() -> AgentState:
    data = test_data_set_A
    requirements_data = {
        field: data.get(field)
        for field in WritingRequirements.model_fields.keys()
    }
    requirements = WritingRequirements(**requirements_data)
    return AgentState(requirements=requirements)

# --- 4. LangGraph 파이프라인 정의 ---
def get_pipeline() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("strategist", generate_strategy_plan_node)
    graph.add_node("drafter", draft_generator_node)
    graph.add_node("metadata_generator", metadata_generator_node)
    graph.add_node("finalizer", finalizer_node)
    graph.set_entry_point("strategist")
    graph.add_edge("strategist", "drafter")
    graph.add_edge("drafter", "metadata_generator")
    graph.add_edge("metadata_generator", "finalizer")
    graph.add_edge("finalizer", END)
    return graph

# --- 5. 테스트 실행 함수 ---
def run_finalizer_node_test():
    logger.info("===== FinalizerNode 통합 테스트 시작 =====")

    initial_state = create_initial_state()
    logger.info("초기 WritingRequirements:\n%s", initial_state.requirements.model_dump_json(indent=2))

    pipeline = get_pipeline().compile()
    final_state_dict: Optional[dict] = None

    for step_output in pipeline.stream(initial_state, {"recursion_limit": 6}):
        node = list(step_output.keys())[0]
        state_dict = step_output[node]
        logger.info(f"[{node}] 노드 실행 완료")
        if node == "finalizer":
            final_state_dict = state_dict

    # --- 6. 결과 검증 ---
    if not final_state_dict:
        logger.error("❌ FinalizerNode까지 도달하지 못했습니다.")
        return

    # final_iteration_output에서 결과 가져오기
    final_output = final_state_dict.get("final_iteration_output", {})
    final_text = final_output.get("final_text")
    next_strategy_prompt = final_output.get("next_strategy_prompt")

    # 검증
    assert final_text and isinstance(final_text, str), "final_text가 생성되지 않았습니다."
    logger.info("✅ final_text 생성 성공 (길이: %d 자)", len(final_text))
    #logger.info("final_text 예시:\n%s", final_text[:200] + "..." if len(final_text) > 200 else final_text)
    logger.info("final_text 예시 전체:\n%s", final_text)

    assert next_strategy_prompt and isinstance(next_strategy_prompt, str), "next_strategy_prompt가 생성되지 않았습니다."
    logger.info("✅ next_strategy_prompt 생성 성공: %s", next_strategy_prompt)

    logger.info("===== FinalizerNode 통합 테스트 완료 =====")

# --- 7. 스크립트 실행 ---
if __name__ == "__main__":
    run_finalizer_node_test()
