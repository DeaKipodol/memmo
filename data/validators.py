from typing import List, Dict
from pydantic import ValidationError
from .data_models import WritingRequirements, CoTStrategyPlan
from  ai_app.assist.common import client, model
import json
import logging
import re
logger = logging.getLogger(__name__)

def get_missing_fields(requirements: WritingRequirements) -> List[str]:
    """
    요구사항 객체에서 값이 비어 있는 필드를 찾아 리스트로 반환합니다.
    """
    return [field for field, value in requirements.model_dump().items() if value is None]

def strip_json_fences(text: str) -> str:
    """마크다운 JSON 코드 블럭 제거"""
    return re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()


def autofill_missing_fields(requirements: WritingRequirements) -> WritingRequirements:
    """
    비어 있는 요구사항 필드들을 감지하고, GPT를 통해 자동 보완한 후
    완성된 WritingRequirements 객체를 반환합니다.
    """
    missing_fields = get_missing_fields(requirements)
    if not missing_fields:
        logger.info("✅ 요구사항이 모두 채워져 있음")
        return requirements
    logger.info("🔄 요구사항 누락 필드 자동 보완 중: %s", missing_fields)
    return autofill_fields_via_gpt(requirements, missing_fields)

def autofill_fields_via_gpt(requirements: WritingRequirements, missing_fields: List[str]) -> WritingRequirements:
    """
    누락된 필드들을 GPT에게 요청하여 자동으로 추정 값을 생성하고, WritingRequirements에 채워 넣는다.
    """
    requirements_dict = requirements.model_dump(exclude_none=True)
    context_summary = json.dumps(requirements_dict, ensure_ascii=False, indent=2)

    for field in missing_fields:
        prompt = (
            f"다음은 사용자의 글쓰기 요구사항입니다. 이 중 일부 항목이 비어 있습니다:\n\n"
            f"{context_summary}\n\n"
            f"위 정보를 바탕으로 누락된 항목 '{field}'에 들어갈 적절한 내용을 작성하세요.\n"
            f"출력은 반드시 아래 JSON 형식처럼 '{field}'만 포함한 순수 JSON 객체여야 하며,\n"
            f"설명문, 마크다운 문법, 기타 부가 텍스트 없이 오직 JSON만 포함해야 합니다:\n"
            f'{{ "{field}": "여기에 내용을 작성하세요." }}'
        )

        try:
            response = client.responses.create(
                model=model.advanced,
                input=[{"role": "user", "content": prompt}],
            )
            content = strip_json_fences(response.output_text.strip())

            if not content.startswith('{'):
                raise ValueError("GPT 응답이 JSON 형식이 아님")

            field_json = json.loads(content)
            if field in field_json:
                setattr(requirements, field, field_json[field])
                logger.info(f"✅ '{field}' 항목 자동 보완 완료: {field_json[field]}")
            else:
                logger.warning(f"⚠️ '{field}' 응답에 값이 포함되지 않았습니다: {response.output_text}")

        except Exception as e:
            logger.error(f"❌ '{field}' 자동 보완 중 오류 발생: {e}")

    return requirements

def flatten_section_plan(section_plan: List[Dict[str, List[str]]]) -> List[str]:
    fields = []
    for section in section_plan:
        fields.extend(section.get("relevant_requirements_fields", []))
    return list(set(fields))

def validate_section_plan_fields(plan: CoTStrategyPlan):
    # Pydantic v2 호환성 처리
    try:
        required_fields = set(WritingRequirements.model_fields.keys())
    except AttributeError:
        required_fields = set(WritingRequirements.__fields__.keys())

    assigned_fields = set(flatten_section_plan(plan.section_plan or []))
    missing_fields = required_fields - assigned_fields

    if missing_fields:
        error_msg = f"Missing fields in section_plan: {', '.join(missing_fields)}"
        raise ValueError(error_msg)
'''
def flatten_section_plan(section_plan: List[Dict[str, List[str]]]) -> List[str]:
    fields = []
    for section in section_plan:
        fields.extend(section.get("relevant_requirements_fields", []))
    return list(set(fields))




def validate_or_autofill_strategy_plan(plan: CoTStrategyPlan, requirements: WritingRequirements) -> CoTStrategyPlan:
    """
    section_plan 검증을 시도하고, 누락 필드가 있으면 requirements를 GPT로 자동 보완한 후 전략 재생성.
    유효한 전략(CoTStrategyPlan)을 반환하거나 실패 시 예외를 그대로 던진다.
    """
    try:
        validate_section_plan_fields(plan)
        logger.info("✅ 전략 검증 통과. 모든 요구사항 필드가 section_plan에 반영됨.")
        return plan

    except ValueError as ve:
        logger.warning("⚠️ 전략 검증 실패: %s", ve)
        missing_fields = parse_missing_fields_from_exception(ve)

        if not missing_fields:
            raise ve  # 필드 누락 외 오류일 경우 그대로 재전파

        logger.info("🔄 누락 필드 자동 보완 시도 중: %s", missing_fields)
        updated_requirements = autofill_fields_via_gpt(requirements, missing_fields)

        logger.info("📤 보완된 요구사항으로 전략 재생성 요청")
        requirements_json = json.dumps(updated_requirements.model_dump(), indent=2, ensure_ascii=False)

        plan_prompt = (
    "다음은 사용자의 글쓰기 요구사항입니다. 이를 기반으로 글쓰기 전략을 JSON 형식으로 작성하세요.\n\n"
    "🎯 반드시 다음 조건을 지키세요:\n"
    "- 출력은 JSON 객체 하나만 포함하세요. 절대 설명, 마크다운(````json`), 예시는 포함하지 마세요.\n"
    "- 각 section에는 반드시 `relevant_requirements_fields` 키가 있어야 하며,\n"
    f"  아래 요구사항의 모든 필드명을 하나 이상 포함해야 합니다 (누락 금지).\n"
    "- 모든 필드를 최소 한 번 이상 `relevant_requirements_fields`에 포함시켜야 합니다:\n"
    f"{list(requirements.model_dump().keys())}\n\n"
    "출력 예시:\n"
    "{\n"
    '  "section_plan": [\n'
    '    {\n'
    '      "section_title": "지원동기",\n'
    '      "content_points": ["지원 배경 설명", "AI 기술 관련 동기"],\n'
    '      "relevant_requirements_fields": ["purpose_background", "context_topic"]\n'
    '    },\n'
    "    ...\n"
    "  ]\n"
    "}\n\n"
    f"🧾 아래는 사용자의 요구사항 JSON입니다. 이 정보를 반영해 전략을 구성하세요:\n{requirements_json}"
)

        try:
            response = client.responses.create(
                model=model.advanced,
                input=[{"role": "user", "content": plan_prompt}],
            )
            clean_json = strip_json_fences(response.output_text)
            new_plan = CoTStrategyPlan.model_validate_json(clean_json)
            validate_section_plan_fields(new_plan)
            logger.info("✅ 전략 재생성 및 검증 통과")
            return new_plan

        except Exception as e:
            logger.error("❌ 전략 재생성 실패: %s", e)
            raise e


def validate_section_plan_fields(plan: CoTStrategyPlan):
    # Pydantic v2 호환성 처리
    try:
        required_fields = set(WritingRequirements.model_fields.keys())
    except AttributeError:
        required_fields = set(WritingRequirements.__fields__.keys())

    assigned_fields = set(flatten_section_plan(plan.section_plan or []))
    missing_fields = required_fields - assigned_fields

    if missing_fields:
        error_msg = f"Missing fields in section_plan: {', '.join(missing_fields)}"
        raise ValueError(error_msg)


def parse_missing_fields_from_exception(exception: ValueError) -> List[str]:
    msg = str(exception)
    if "Missing fields in section_plan:" in msg:
        return [field.strip() for field in msg.split(":", 1)[1].split(",")]
    return []

'''