import sys
import os
import logging
import json
from typing import Optional

# --- 1. 경로 설정 및 기본 설정 ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

# --- 2. 필요한 모듈 임포트 ---
from langgraph.graph import StateGraph, END
from data.data_models import AgentState, WritingRequirements
from data.sampleRequirements import test_data_set_C

from ai_app.Result_generation.Generate_strategy_plan_node import generate_strategy_plan_node
from ai_app.Result_generation.DraftGeneratorNode import draft_generator_node
from ai_app.Result_generation.MetadataGeneratorNode import metadata_generator_node  # ✅ 새로 추가된 노드

# --- 3. 초기 상태 생성 ---
def create_initial_state() -> AgentState:
    requirements_data = {
        field: test_data_set_C.get(field)
        for field in WritingRequirements.model_fields.keys()
    }
    requirements = WritingRequirements(**requirements_data)
    return AgentState(requirements=requirements)

# --- 4. LangGraph 테스트 파이프라인 정의 ---
def get_pipeline() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("strategist", generate_strategy_plan_node)
    graph.add_node("drafter", draft_generator_node)
    graph.add_node("metadata_generator", metadata_generator_node)
    graph.set_entry_point("strategist")
    graph.add_edge("strategist", "drafter")
    graph.add_edge("drafter", "metadata_generator")
    graph.add_edge("metadata_generator", END)
    return graph

# --- 5. 실행 함수 ---
def run_metadata_node_test():
    logger.info("===== MetadataGeneratorNode 테스트 시작 =====")

    initial_state = create_initial_state()
    graph = get_pipeline().compile()

    final_state = None
    for step_output in graph.stream(initial_state, {"recursion_limit": 6}):
        node = list(step_output.keys())[0]
        state = step_output[node]

        logger.info(f"[{node}] 노드 실행 완료")
        if node == "metadata_generator":
            final_state = state

    if final_state and final_state.get("draft_metadata"):
        logger.info("✅ 메타데이터 생성 성공")
        for i, meta in enumerate(final_state["draft_metadata"]):
            logger.info(f"--- 메타데이터 {i+1} ---")
            logger.info(json.dumps(meta, indent=2, ensure_ascii=False))
    else:
        logger.error("❌ 메타데이터 생성 실패 또는 누락됨")
        if final_state and final_state.get("error_message"):
            logger.error("에러 메시지: %s", final_state["error_message"])

    logger.info("===== MetadataGeneratorNode 테스트 종료 =====")

# --- 6. 실행 ---
if __name__ == "__main__":
    run_metadata_node_test()
