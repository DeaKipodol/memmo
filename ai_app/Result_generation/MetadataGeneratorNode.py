# MetadataGeneratorNode.py
import logging
from typing import List, Dict
from data.data_models import AgentState, WritingRequirements, CoTStrategyPlan
from ai_app.assist.common import client, model
import re
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

def get_identified_weakness(draft_text: str) -> str:
    """GPT를 통해 초안의 약점 자동 생성"""
    try:
        response = client.responses.create(
            model=model.advanced,
            input=[
                {"role": "system", "content": "당신은 글쓰기 평가 전문가입니다."},
                {"role": "user", "content": f"""다음 초안의 약점이나 개선 가능성을 1~2문장으로 요약하세요.\n\n초안:\n{draft_text}"""}
            ],
            text={"format": {"type": "text"}}
        )
        return response.output_text.strip()
    except Exception as e:
        logger.warning(f"약점 평가 실패: {e}")
        return "약점 분석 실패"

def generate_metadata_per_section(
    draft_texts: List[str],
    section_plan: List[dict],
    requirements: WritingRequirements,
    strategy: CoTStrategyPlan
) -> List[Dict]:
    metadata_list = []

    # 약점 분석 병렬 실행
    with ThreadPoolExecutor() as executor:
        weaknesses = list(executor.map(get_identified_weakness, draft_texts))

    for section, draft, weakness in zip(section_plan, draft_texts, weaknesses):
        relevant_fields = section.get("relevant_requirements_fields", [])
        related_reqs = {
            field: getattr(requirements, field)
            for field in relevant_fields
            if getattr(requirements, field, None)
        }

        metadata = {
            "section_name": section.get("section_name"),
            "purpose_or_goal": section.get("purpose_or_goal"),
            "writing_guideline": section.get("writing_guideline_or_flow"),
            "related_requirements": related_reqs,
            "identified_weakness": weakness,
            "example_text": draft
        }
        metadata_list.append(metadata)

    return metadata_list

def metadata_generator_node(state: AgentState) -> AgentState:
    """메타데이터 생성 노드 (안정적인 파싱 및 병렬 분석 적용)"""
    logger.info("🧠 MetadataGeneratorNode 실행 시작")
    try:
        full_draft = state.current_draft_text.strip()
        drafts = re.split(r"\[.*?\]:\n", full_draft)[1:]
        draft_texts = [d.strip() for d in drafts]

        if len(draft_texts) != len(state.generated_strategy_plan.section_plan):
            logger.warning("섹션 계획과 파싱된 초안의 개수가 일치하지 않습니다. 파싱 로직을 확인하세요.")

        metadata = generate_metadata_per_section(
            draft_texts=draft_texts,
            section_plan=state.generated_strategy_plan.section_plan,
            requirements=state.requirements,
            strategy=state.generated_strategy_plan
        )
        state.draft_metadata = metadata
        state.current_operation_step = "메타데이터 생성 완료"
        logger.info("✅ 메타데이터 생성 완료")
    except Exception as e:
        logger.exception("❌ 메타데이터 생성 실패")
        state.error_message = f"메타데이터 생성 실패: {str(e)}"
    return state
