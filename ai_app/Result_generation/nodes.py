# ai_app/Result_generation/nodes.py

import os
import sys
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.append(project_root)
import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from data.data_models import AgentState

# 각 노드 함수 import
from ai_app.Result_generation.Generate_strategy_plan_node import generate_strategy_plan_node
from ai_app.Result_generation.DraftGeneratorNode import draft_generator_node
from ai_app.Result_generation.MetadataGeneratorNode import metadata_generator_node
from ai_app.Result_generation.FinalizerNode import finalizer_node

logger = logging.getLogger(__name__)

def build_pipeline() -> StateGraph:
    """AgentState → 최종 결과까지 이어지는 LangGraph 파이프라인을 반환합니다."""
    graph = StateGraph(AgentState)

    # 1) 노드 등록
    graph.add_node("strategist", generate_strategy_plan_node)
    graph.add_node("drafter", draft_generator_node)
    graph.add_node("metadata_generator", metadata_generator_node)
    graph.add_node("finalizer", finalizer_node)

    # 2) 실행 순서(에지) 정의
    graph.set_entry_point("strategist")
    graph.add_edge("strategist", "drafter")
    graph.add_edge("drafter", "metadata_generator")
    graph.add_edge("metadata_generator", "finalizer")
    graph.add_edge("finalizer", END)

    return graph

# --- 선택적: 간단 실행 헬퍼 --------------------------------------------------
def run_pipeline(initial_state: AgentState, recursion_limit: int = 6) -> Dict[str, Any]:
    """
    한 번에 파이프라인을 실행하고 마지막 상태(dict)를 반환합니다.
    """
    pipeline = build_pipeline().compile()
    final_state_dict = pipeline.invoke(initial_state, {"recursion_limit": recursion_limit})
    return final_state_dict

# --- 선택적: 모듈 직접 실행 시 간단 데모 --------------------------------------
if __name__ == "__main__":
    import json
    from data.sampleRequirements import test_data_set_C
    from data.data_models import WritingRequirements

    logging.basicConfig(level=logging.INFO)

    # 샘플 요구사항으로 초기 상태 구성
    requirements = WritingRequirements(**{
        field: test_data_set_C.get(field)
        for field in WritingRequirements.model_fields.keys()
    })
    initial_state = AgentState(requirements=requirements)

    # 파이프라인 실행
    final_state = run_pipeline(initial_state)

    # 결과 출력
    print("\n=== 최종 결과 ===")
    print(json.dumps(final_state.get("final_iteration_output", {}), ensure_ascii=False, indent=2))
