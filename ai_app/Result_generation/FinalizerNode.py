# ai_app/Result_generation/FinalizerNode.py
import logging
from typing import List, Dict
from data.data_models import AgentState, WritingRequirements, CoTStrategyPlan
from ai_app.assist.common import client, model

logger = logging.getLogger(__name__)

def build_final_prompt(
    requirements: WritingRequirements,
    strategy: CoTStrategyPlan,
    metadata: List[Dict],
    draft: str
) -> str:
    """
    모델의 instructions로 사용할 시스템 프롬프트를 생성합니다.
    1) 전체 요구사항 블록
    2) 전략 정보 블록
    3) 섹션별 메타데이터 요약 (related_requirements 키 목록만)
    4) 초안 블록
    5) 사용자 지시문
    """
    # 1) 전체 요구사항
    reqs = "\n".join(f"- {k}: {v}" for k, v in requirements.model_dump().items())
    req_block = f"[Requirements]\n{reqs}\n"

    # 2) 전략 정보
    strat = (
        f"- writing_type: {strategy.writing_type}\n"
        f"- core_message: {strategy.core_message}\n"
        f"- target_audience_insight: {strategy.target_audience_insight}\n"
        f"- tone_and_manner: {strategy.tone_and_manner}\n"
        f"- constraints_to_observe: {', '.join(strategy.constraints_to_observe)}\n"
    )
    strat_block = f"[Strategy]\n{strat}\n"

    # 3) 메타데이터 요약
    meta_lines = []
    for m in metadata:
        # related_requirements 키 목록만 사용
        fields = ",".join(m["related_requirements"].keys())
        meta_lines.append(
            f"{m['section_name']} | purpose: {m['purpose_or_goal']} "
            f"| fields: [{fields}] | weakness: {m['identified_weakness']}"
        )
    meta_block = "[Metadata]\n" + "\n".join(meta_lines) + "\n"

    # 4) 초안
    draft_block = f"[Draft]\n{draft}\n"

    # 5) 사용자 지시문
    user_msg = (
        "위 정보를 모두 참고하여 identified_weakness를 보완하고,\n"
        "전략과 제약을 준수하며 섹션 목적에 충실한 최종 글을 작성해주세요."
    )
    user_block = f"[User]\n{user_msg}"

    # instructions로 사용할 하나의 문자열로 합치기
    return "\n".join([req_block, strat_block, meta_block, draft_block, user_block])

def call_llm_for_final_text(instructions: str) -> str:
    """
    Responses API의 instructions/input 구분을 사용해 LLM 호출
    - instructions: build_final_prompt로 생성한 시스템 지침
    - input: 실제 사용자 요청 (간략하게)
    """
    response = client.responses.create(
        model=model.advanced,
        instructions=instructions,
        input="최종 결과물을 텍스트로 반환해주세요.",
        text={"format": {"type": "text"}}
    )
    return response.output_text.strip()

def refine_final_text(text: str) -> str:
    """
    글자 수는 그대로 유지하되, '인공지능이 쓴 듯한' 어투 없이
    자연스럽게 다시 출력하도록 LLM에 요청하는 보정 함수입니다.
    """
    refine_instructions = (
        "아래 글을 글자 수를 변경하지 않고, "
        "인공지능이 쓴 듯한 표현을 제거하여 자연스럽게 재작성해 주세요.\n\n"
        f"{text}"
    )
    response = client.responses.create(
        model=model.advanced,
        instructions=refine_instructions,
        input="보정된 텍스트를 반환해주세요.",
        text={"format": {"type": "text"}}
    )
    return response.output_text.strip()

def finalizer_node(state: AgentState) -> AgentState:
    """최종 결과물(final_text)과 전략 요약(final_summary)을 생성하는 노드"""
    logger.info("🧠 FinalizerNode 실행 시작")
    # 1) 입력 데이터 준비
    requirements = state.requirements
    strategy = state.generated_strategy_plan
    metadata = state.draft_metadata
    draft = state.current_draft_text

    # 2) instructions 생성
    instructions = build_final_prompt(
        requirements=requirements,
        strategy=strategy,
        metadata=metadata,
        draft=draft
    )

    try:
        # 3) LLM 호출
        raw_text = call_llm_for_final_text(instructions)

        # 2) 두 번째 LLM 호출: 보정
        refined_text = refine_final_text(raw_text)
       # 4) 상태 업데이트: final_iteration_output Dict에 담기
        state.final_iteration_output = {
            "final_text": refined_text,
            "next_strategy_prompt": f"전략 요약: {strategy.core_message}"
        }
        state.current_operation_step = "최종화 완료"
    except Exception as e:
        logger.exception("❌ FinalizerNode 오류")
        state.error_message = f"FinalizerNode 오류: {e}"
    return state
